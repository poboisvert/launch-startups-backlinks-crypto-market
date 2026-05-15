from datetime import timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from matplotlib.ticker import FuncFormatter

from data import log_func

# Define constants
COLORS_LABELS = {
    "#c00200": "Maximum bubble territory",
    "#d64018": "Sell. Seriously, SELL!",
    "#ed7d31": "FOMO Intensifies",
    "#f6b45a": "Is this a bubble?",
    "#feeb84": "HODL!",
    "#b1d580": "Still cheap",
    "#63be7b": "Accumulate",
    "#54989f": "BUY!",
    "#4472c4": "Fire sale!",
}
BAND_WIDTH = 0.3
NUM_BANDS = 9
FIGURE_SIZE = (15, 7)
BACKGROUND_COLOR = "#0d1117"
EXTEND_MONTHS = 9

HALVING_DATES = [
    pd.Timestamp("2012-11-28"),
    pd.Timestamp("2016-07-09"),
    pd.Timestamp("2020-05-11"),
    pd.Timestamp("2024-04-20"),
]


def format_price(y: float) -> str:
    """Format a USD price for tooltips and labels."""
    if y < 1:
        return f"${y:.2f}"
    if y < 10:
        return f"${y:.1f}"
    if y < 1_000:
        return f"${int(y):,}"
    if y < 1_000_000:
        s = f"${y / 1_000:.1f}K"
        return s.replace(".0K", "K")
    s = f"${y / 1_000_000:.1f}M"
    return s.replace(".0M", "M")


def compute_bands(raw_data, popt, num_bands=NUM_BANDS, band_width=BAND_WIDTH):
    """
    Compute rainbow band bounds over an extended date range.

    Returns:
        extended_dates (pd.Series): Dates including forward projection.
        bands (list[dict]): Each dict has label, color, lower, upper (numpy arrays).
    """
    extended_dates = extend_dates(raw_data)
    extended_xdata = np.arange(1, len(extended_dates) + 1)
    extended_fitted_ydata = log_func(extended_xdata, *popt)

    colors = list(COLORS_LABELS.keys())[::-1]
    labels = list(COLORS_LABELS.values())[::-1]
    i_decrease = 1.5
    bands = []
    for i in range(num_bands):
        lower = np.exp(
            extended_fitted_ydata + (i - i_decrease) * band_width - band_width
        )
        upper = np.exp(extended_fitted_ydata + (i - i_decrease) * band_width)
        bands.append(
            {
                "label": labels[i],
                "color": colors[i],
                "lower": lower,
                "upper": upper,
            }
        )
    return extended_dates, bands


def band_at_price(price: float, bands: list[dict], index: int = -1) -> str | None:
    """Return the band label for a price on the last (or given) day index."""
    for band in bands:
        if band["lower"][index] <= price <= band["upper"][index]:
            return band["label"]
    return None


def create_interactive_plot(raw_data, popt):
    """
    Build an interactive Plotly chart with hoverable band price ranges.

    Returns:
        plotly.graph_objects.Figure
    """
    extended_dates, bands = compute_bands(raw_data, popt)
    dates = pd.to_datetime(extended_dates)

    fig = go.Figure()

    for band in bands:
        hover_upper = [format_price(v) for v in band["upper"]]
        hover_lower = [format_price(v) for v in band["lower"]]
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=band["upper"],
                mode="lines",
                line=dict(width=0),
                showlegend=True,
                name=band["label"],
                legendgroup=band["label"],
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=band["lower"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=band["color"],
                showlegend=False,
                legendgroup=band["label"],
                customdata=np.column_stack([hover_upper, hover_lower]),
                hovertemplate=(
                    f"<b>{band['label']}</b><br>"
                    "%{x|%b %d, %Y}<br>"
                    "Upper: %{customdata[0]}<br>"
                    "Lower: %{customdata[1]}"
                    "<extra></extra>"
                ),
            )
        )

    date_to_idx = {d: i for i, d in enumerate(dates)}
    price_hover = []
    for _, row in raw_data.iterrows():
        idx = date_to_idx.get(pd.Timestamp(row["Date"]), -1)
        zone = band_at_price(row["Value"], bands, index=idx) if idx >= 0 else None
        zone_text = f"<br>Band: {zone}" if zone else ""
        price_hover.append(
            f"<b>BTC Price</b><br>"
            f"{row['Date']:%b %d, %Y}<br>"
            f"Price: {format_price(row['Value'])}"
            f"{zone_text}"
        )

    fig.add_trace(
        go.Scatter(
            x=raw_data["Date"],
            y=raw_data["Value"],
            mode="lines",
            name="BTC Price",
            line=dict(color="white", width=2),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=price_hover,
        )
    )

    last = raw_data.loc[raw_data["Date"].idxmax()]
    fig.add_trace(
        go.Scatter(
            x=[last["Date"]],
            y=[last["Value"]],
            mode="markers",
            name="Current price",
            marker=dict(color="white", size=10, line=dict(color=BACKGROUND_COLOR, width=2)),
            showlegend=False,
            hovertemplate=(
                f"<b>Latest</b><br>"
                f"{last['Date']:%b %d, %Y}<br>"
                f"Price: {format_price(last['Value'])}<br>"
                f"Band: {band_at_price(last['Value'], bands) or '—'}"
                "<extra></extra>"
            ),
        )
    )

    for halving_date in HALVING_DATES:
        fig.add_vline(
            x=halving_date,
            line=dict(color="white", width=1),
            opacity=0.5,
        )

    fig.update_layout(
        title=dict(text="Bitcoin Rainbow Chart", font=dict(color="white", size=18)),
        template="plotly_dark",
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="white"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161b22", font_size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=30, t=80, b=50),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            spikemode="across",
            spikesnap="cursor",
            showspikes=True,
            spikecolor="rgba(255,255,255,0.35)",
        ),
        yaxis=dict(
            type="log",
            title="Price (USD)",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            tickformat=",.0f",
            exponentformat="none",
        ),
        height=700,
    )

    fig.update_xaxes(
        range=[
            raw_data["Date"].min(),
            raw_data["Date"].max() + pd.DateOffset(months=EXTEND_MONTHS),
        ]
    )
    fig.update_yaxes(range=[np.log10(0.01), None])

    return fig


def create_plot(raw_data, popt):

    # Create plot
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    # Plot rainbow bands and price data
    plot_rainbow(ax, raw_data, popt)
    plot_price(ax, raw_data)

    # Add halving lines
    add_halving_lines(ax)

    # Configure plot appearance
    configure_plot(ax, raw_data)

    add_legend(ax)


def add_halving_lines(ax):
    """Add vertical lines for Bitcoin halving events."""
    for halving_date in HALVING_DATES:
        ax.axvline(halving_date, color="white", linestyle="-", linewidth=1, alpha=0.5)


def extend_dates(raw_data, months=EXTEND_MONTHS):
    """
    Extend the date range of the data by a specified number of months.

    Args:
        raw_data (pd.DataFrame): Original data.
        months (int): Number of months to extend.

    Returns:
        pd.Series: Extended date range.
    """
    last_date = raw_data["Date"].max()
    extended_dates = pd.date_range(
        start=last_date + timedelta(days=1), periods=months * 30
    )
    return pd.concat([raw_data["Date"], pd.Series(extended_dates)])


def plot_rainbow(ax, raw_data, popt, num_bands=NUM_BANDS, band_width=BAND_WIDTH):
    """
    Plot rainbow bands on the given axis.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to plot on.
        raw_data (pd.DataFrame): Raw data.
        num_bands (int): Number of bands.
        band_width (float): Width of each band.
    """
    extended_dates, bands = compute_bands(
        raw_data, popt, num_bands=num_bands, band_width=band_width
    )

    legend_handles = []
    for band in bands:
        ax.fill_between(
            extended_dates,
            band["lower"],
            band["upper"],
            alpha=1,
            color=band["color"],
            label=band["label"],
        )
        legend_handles.append(
            plt.Line2D([0], [0], color=band["color"], lw=4, label=band["label"])
        )
    return legend_handles


def plot_price(ax, raw_data):
    """
    Plot Bitcoin price data on the given axis.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to plot on.
        raw_data (pd.DataFrame): Raw data.

    Returns:
        matplotlib.lines.Line2D: The line representing the BTC price.
    """
    line = ax.semilogy(
        raw_data["Date"].values,
        raw_data["Value"].values,
        color="white",
        label="BTC Price",
    )[0]
    last = raw_data.loc[raw_data["Date"].idxmax()]
    ax.plot(
        last["Date"],
        last["Value"],
        marker="o",
        color="white",
        markersize=9,
        markeredgecolor=BACKGROUND_COLOR,
        markeredgewidth=1.5,
        linestyle="none",
        zorder=line.get_zorder() + 1,
        clip_on=True,
    )
    return line


def y_format(y, _):
    """Custom formatter for Y-axis labels."""
    return format_price(y).replace(",", ".")


def configure_plot(ax, raw_data):
    """
    Configure the appearance of the plot.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to configure.
        raw_data (pd.DataFrame): Raw data.
    """
    formatter = FuncFormatter(y_format)
    ax.yaxis.set_major_formatter(formatter)
    ax.set_ylim(bottom=0.01)
    ax.set_xlim(
        [
            raw_data["Date"].min(),
            raw_data["Date"].max() + pd.DateOffset(months=EXTEND_MONTHS),
        ]
    )
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")

    # Set x-axis major ticks to every year
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Rotate and align the tick labels for better readability
    plt.setp(ax.get_xticklabels(), rotation=0)


def add_legend(ax):
    # Create custom legend handles with square markers, including BTC price
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color=BACKGROUND_COLOR,
            markerfacecolor="white",
            markersize=10,
            label="BTC price",
        )
    ] + [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color=BACKGROUND_COLOR,
            markerfacecolor=color,
            markersize=10,
            label=label,
        )
        for color, label in zip(
            list(COLORS_LABELS.keys()), list(COLORS_LABELS.values())
        )
    ]

    # Add legend
    legend = ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.15),
        ncol=len(legend_handles),
        frameon=False,
        fontsize="small",
        labelcolor="white",
    )

    # Make legend text bold
    for text in legend.get_texts():
        text.set_fontweight("bold")

    # Adjust layout to reduce empty space around the plot
    plt.subplots_adjust(left=0.05, right=0.975, top=0.875, bottom=0.1)
