import argparse

import matplotlib.pyplot as plt
from plot import create_interactive_plot, create_plot, show_interactive_fig, write_interactive_html

from data import get_data


def main(
    save: bool = False,
    html: str | None = None,
    file_path: str = "img/bitcoin_rainbow_chart.png",
    *,
    data_csv: str = "data/bitcoin_data.csv",
    full_refresh: bool = False,
):
    raw_data, popt = get_data(data_csv, full_refresh=full_refresh)

    if save:
        create_plot(raw_data, popt)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        print(f"Saved {file_path}")
        return

    fig = create_interactive_plot(raw_data, popt)

    if html:
        write_interactive_html(fig, html)
        print(f"Saved interactive chart to {html}")
    else:
        show_interactive_fig(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bitcoin rainbow chart")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Reload BTC/USD daily prices from 2009-01-02 through today (CryptoCompare)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Write static PNG to img/bitcoin_rainbow_chart.png (matplotlib)",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        default=None,
        help="Write interactive HTML chart (e.g. img/chart.html)",
    )
    args = parser.parse_args()
    main(save=args.save, html=args.html, full_refresh=args.full_refresh)
