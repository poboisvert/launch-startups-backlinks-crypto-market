import datetime
import time
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
import requests
from dateutil.parser import parse
from scipy.optimize import curve_fit

# First calendar day with a known genesis-adjacent history in many datasets;
# USD market data from APIs typically begins later — missing days stay 0 until first quote.
BTC_HISTORY_START = pd.Timestamp("2009-01-02")
CRYPTOCOMPARE_HISTODAY = "https://min-api.cryptocompare.com/data/v2/histoday"
CRYPTOCOMPARE_PAGE_LIMIT = 2000


def log_func(x, a, b, c):
    """Logarithmic function for curve fitting."""
    return a * np.log(b + x) + c


def _utc_midnight(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts).normalize()
    if t.tzinfo is not None:
        return t.tz_convert("UTC").normalize().tz_localize(None)
    return t


def _to_unix_utc_start_of_day(naive_date: pd.Timestamp) -> int:
    """Naive calendar date interpreted as UTC midnight."""
    return int(pd.Timestamp(naive_date).tz_localize("UTC").timestamp())


def _cryptocompare_histoday_page(
    to_ts: int, session: requests.Session
) -> list[dict]:
    params = {
        "fsym": "BTC",
        "tsym": "USD",
        "limit": CRYPTOCOMPARE_PAGE_LIMIT,
        "toTs": to_ts,
    }
    r = session.get(CRYPTOCOMPARE_HISTODAY, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("Response") != "Success":
        raise RuntimeError(
            f"CryptoCompare error: {payload.get('Message', payload)}"
        )
    return payload.get("Data", {}).get("Data") or []


def load_btc_daily_usd_cryptocompare(
    start: str | pd.Timestamp | datetime.datetime,
    end: str | pd.Timestamp | datetime.datetime | None = None,
    *,
    sleep_between_pages: float = 0.25,
) -> pd.DataFrame:
    """
    Daily BTC/USD close from CryptoCompare ``histoday`` (paginated).

    Fills every calendar day from ``start`` through ``end`` with 0 where the
    API has no candle (early years), matching ``Date,Value`` CSV style.
    """
    start_d = _utc_midnight(start)
    end_d = _utc_midnight(end if end is not None else pd.Timestamp.utcnow())
    today_utc = _utc_midnight(pd.Timestamp.utcnow())
    if end_d > today_utc:
        end_d = today_utc
    if start_d > end_d:
        return pd.DataFrame(columns=["Date", "Value"])

    start_unix = _to_unix_utc_start_of_day(start_d)
    session = requests.Session()
    session.headers.update(
        {"Accept": "application/json", "User-Agent": "bitcoin-rainbow-chart/1.0"}
    )

    to_ts = int(
        (pd.Timestamp(end_d).tz_localize("UTC") + pd.Timedelta(days=1)).timestamp()
    )
    all_candles: list[dict] = []
    while True:
        batch = _cryptocompare_histoday_page(to_ts, session)
        if not batch:
            break
        all_candles.extend(batch)
        oldest = batch[0]["time"]
        if oldest <= start_unix:
            break
        to_ts = oldest - 1
        time.sleep(sleep_between_pages)

    if not all_candles:
        idx = pd.date_range(start=start_d, end=end_d, freq="D")
        return pd.DataFrame({"Date": idx, "Value": 0.0})

    df = pd.DataFrame(all_candles)
    df["Date"] = (
        pd.to_datetime(df["time"], unit="s", utc=True)
        .dt.normalize()
        .dt.tz_localize(None)
    )
    df = df.rename(columns={"close": "Value"})[["Date", "Value"]]
    df = df.drop_duplicates(subset=["Date"], keep="last")
    df = df[(df["Date"] >= start_d) & (df["Date"] <= end_d)]

    full_idx = pd.date_range(start=start_d, end=end_d, freq="D")
    df = (
        df.set_index("Date")
        .reindex(full_idx)
        .rename_axis("Date")
        .reset_index()
    )
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0.0)
    return df


def get_data(file_path: str | Path, full_refresh: bool = False):
    """
    Load and preprocess data from a CSV file.

    Args:
        file_path (str): Path to the CSV file.
        full_refresh: If True, reload BTC/USD daily from 2009-01-02 through today
            via CryptoCompare and overwrite the CSV.

    Returns:
        pd.DataFrame: Processed data.
        np.ndarray: Fitted Y data.
    """
    path = Path(file_path)

    if full_refresh or not path.exists():
        print(
            "Loading full BTC/USD daily history (2009-01-02 → today) via CryptoCompare..."
        )
        raw_data = load_btc_daily_usd_cryptocompare(BTC_HISTORY_START, None)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw_data.to_csv(path, index=False)
    else:
        raw_data = pd.read_csv(path)
        raw_data["Date"] = pd.to_datetime(raw_data["Date"])

        last = raw_data["Date"].max().normalize()
        today_utc = pd.Timestamp.utcnow().normalize()
        diff_days = (today_utc - last).days

        if diff_days > 1:
            print(f"Data is {diff_days} days old. Updating via CryptoCompare...")
            new_data = load_btc_daily_usd_cryptocompare(
                last + pd.Timedelta(days=1), today_utc
            )
            if not new_data.empty:
                raw_data = pd.concat([raw_data, new_data], ignore_index=True)
                raw_data = raw_data.drop_duplicates(subset=["Date"], keep="last")
                raw_data = raw_data.sort_values("Date").reset_index(drop=True)
                raw_data.to_csv(path, index=False)

    raw_data = raw_data[raw_data["Value"] > 0]

    # Prepare data for curve fitting
    xdata = np.array([x + 1 for x in range(len(raw_data))])
    ydata = np.log(raw_data["Value"])

    # Fit the logarithmic curve
    popt, _ = curve_fit(log_func, xdata, ydata)

    return raw_data, popt


# Save the exchanges that are useful
exchanges_with_ohlcv = []

for exchange_id in ccxt.exchanges:
    exchange = getattr(ccxt, exchange_id)()
    if exchange.has["fetchOHLCV"]:
        exchanges_with_ohlcv.append(exchange_id)


def fetch_data(
    exchange: str = "binance",
    since=None,
    limit: int = None,
) -> pd.DataFrame:
    """
    Pandas DataFrame with the latest OHLCV data from specified exchange.

    Parameters
    --------------
    exchange : string, check the exchange_list to see the supported exchanges. For instance "binance".
    since: integer, UTC timestamp in milliseconds. Default is None, which means will not take the start date into account.
    The behavior of this parameter depends on the exchange.
    limit : integer, the amount of rows that should be returned. For instance 100, default is None, which means 500 rows.

    All the timeframe options are: '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'
    """

    timeframe: str = "1d"
    symbol: str = "BTC/USDT"

    # If it is a string, convert it to a datetime object
    if isinstance(since, str):
        since = parse(since)

    if isinstance(since, datetime.datetime):
        since = int(since.timestamp() * 1000)

    # Always convert to lowercase
    exchange = exchange.lower()

    if exchange not in exchanges_with_ohlcv:
        raise ValueError(
            f"{exchange} is not a supported exchange. Please use one of the following: {exchanges_with_ohlcv}"
        )

    exchange = getattr(ccxt, exchange)()

    # Convert ms to seconds, so we can use time.sleep() for multiple calls
    rate_limit = exchange.rateLimit / 1000

    # Get data
    data = exchange.fetch_ohlcv(symbol, timeframe, since, limit)

    while len(data) < limit:
        # If the data is less than the limit, we need to make multiple calls
        # Shift the since date to the last date of the data
        since = data[-1][0] + 86400000

        # Sleep to prevent rate limit errors
        time.sleep(rate_limit)

        # Get the remaining data
        new_data = exchange.fetch_ohlcv(symbol, timeframe, since, limit - len(data))
        data += new_data

        if len(new_data) == 0:
            break

    df = pd.DataFrame(
        data, columns=["Timestamp", "open", "high", "low", "close", "volume"]
    )

    # Convert Timestamp to date
    df.Timestamp = (
        df.Timestamp / 1000
    )  # Timestamp is 1000 times bigger than it should be in this case
    df["Date"] = pd.to_datetime(df.Timestamp, unit="s")

    # The default values are string, so convert these to numeric values
    df["Value"] = pd.to_numeric(df["close"])

    # Returned DataFrame should consists of columns: index starting from 0, date as datetime, open, high, low, close, volume in numbers
    return df[["Date", "Value"]]
