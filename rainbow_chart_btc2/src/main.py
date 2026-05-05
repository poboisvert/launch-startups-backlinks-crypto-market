import argparse

import matplotlib.pyplot as plt
from plot import create_plot

from data import get_data


def main(
    save: bool = False,
    file_path: str = "img/bitcoin_rainbow_chart.png",
    *,
    data_csv: str = "data/bitcoin_data.csv",
    full_refresh: bool = False,
):
    # Load data
    raw_data, popt = get_data(data_csv, full_refresh=full_refresh)

    # Create plot
    create_plot(raw_data, popt)

    # Show plot
    if save:
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
    else:
        plt.show()


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
        help="Write PNG to img/bitcoin_rainbow_chart.png instead of showing a window",
    )
    args = parser.parse_args()
    main(save=args.save, full_refresh=args.full_refresh)
