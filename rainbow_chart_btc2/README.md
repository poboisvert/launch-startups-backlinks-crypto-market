# Bitcoin rainbow chart

Small Python tool that plots the classic **log-scale rainbow bands** over BTC/USD with an **interactive** chart (hover any date to see each band’s upper/lower price), or export PNG/HTML.

**Data:** daily closes from [CryptoCompare](https://www.cryptocompare.com/) (`histoday`), from **2009-01-02** through today. Days before the API has prices are stored as `0` and skipped for the fit (same idea as the bundled CSV).

## Preview

![Bitcoin rainbow chart example](img/bitcoin_rainbow_chart.png)

## Setup

Use a virtual environment (recommended on macOS):

```bash
cd btc
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run everything from the **`btc`** folder so paths like `data/bitcoin_data.csv` resolve.

## Run

```bash
python src/main.py
```

Opens an interactive Plotly chart in your browser (hover for band prices; click legend to toggle bands; zoom/pan).

```bash
python src/main.py --html img/chart.html
```

Writes a standalone interactive HTML file.

```bash
python src/main.py --save
```

Writes `img/bitcoin_rainbow_chart.png` (static matplotlib image).

```bash
python src/main.py --full-refresh
```

Re-downloads the full daily series and overwrites `data/bitcoin_data.csv` (can take a bit; CryptoCompare rate limits apply).

## Credits

Based on [StephanAkkerman/bitcoin-rainbow-chart](https://github.com/StephanAkkerman/bitcoin-rainbow-chart). Rainbow idea and similar charts: [LookIntoBitcoin](https://www.lookintobitcoin.com/charts/bitcoin-rainbow-chart/), [Blockchain Center](https://www.blockchaincenter.net/en/bitcoin-rainbow-chart/).
