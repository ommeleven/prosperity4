#!/usr/bin/env python3
"""Plot bid-ask spreads for selected VEV voucher products."""

from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def load_prices(data_dir: Path, days):
    dfs = []
    for day in days:
        filename = data_dir / f'prices_round_3_day_{day}.csv'
        if not filename.exists():
            raise FileNotFoundError(f'Could not find price file: {filename}')
        df = pd.read_csv(filename, sep=';')
        df['day'] = df['day'].astype(int)
        df['timestamp'] = df['timestamp'].astype(int)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def compute_spread(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['spread'] = df['ask_price_1'] - df['bid_price_1']
    df.loc[df[['ask_price_1', 'bid_price_1']].isnull().any(axis=1), 'spread'] = pd.NA
    return df


def plot_spreads(df: pd.DataFrame, products, save_path: Path | None = None):
    sns.set_style('whitegrid')
    selected = df[df['product'].isin(products)].copy()
    if selected.empty:
        raise ValueError(f'No rows found for products: {products}')

    days = sorted(selected['day'].unique())
    fig, axes = plt.subplots(len(products), 1, figsize=(12, 4 * len(products)), sharex=True)
    if len(products) == 1:
        axes = [axes]

    for ax, product in zip(axes, products):
        product_data = selected[selected['product'] == product]
        for day in days:
            day_data = product_data[product_data['day'] == day]
            ax.plot(day_data['timestamp'], day_data['spread'], marker='o', linestyle='-', label=f'Day {day}')
        ax.set_title(f'{product} bid-ask spread')
        ax.set_ylabel('Spread')
        ax.legend()
        ax.grid(True)

    axes[-1].set_xlabel('Timestamp')
    plt.tight_layout()

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150)
        print(f'Saved spread plot to: {save_path}')
    else:
        plt.show()


def print_summary(df: pd.DataFrame, products):
    print('Spread summary:')
    for product in products:
        product_data = df[df['product'] == product]
        if product_data.empty:
            print(f'  - {product}: no data')
            continue
        spread_series = product_data['spread'].dropna()
        if spread_series.empty:
            print(f'  - {product}: all spread values missing')
            continue
        print(f'  - {product}: count={len(spread_series)}, min={spread_series.min():.2f}, max={spread_series.max():.2f}, mean={spread_series.mean():.2f}')


def main():
    parser = argparse.ArgumentParser(description='Plot VEV voucher bid-ask spreads for round 3.')
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).parent,
                        help='Directory containing prices_round_3_day_*.csv files')
    parser.add_argument('--products', nargs='+', default=['VEV_5500', 'VEV_6000', 'VEV_6500', 'VEV_5400'],
                        help='Voucher products to plot')
    parser.add_argument('--days', nargs='+', type=int, default=[0, 1, 2],
                        help='Day numbers to include')
    parser.add_argument('--save', type=Path, default=None,
                        help='Save the output plot to a PNG file instead of showing it')
    args = parser.parse_args()

    prices = load_prices(args.data_dir, args.days)
    prices = compute_spread(prices)
    print_summary(prices, args.products)
    plot_spreads(prices, args.products, save_path=args.save)


if __name__ == '__main__':
    main()
