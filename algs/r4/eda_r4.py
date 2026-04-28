import pandas as pd
import numpy as np
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Load all data
prices_data = []
trades_data = []

for day in [1, 2, 3]:
    prices_data.append(pd.read_csv(f'/Users/HP/src/prosperity4/algs/r4/prices_round_4_day_{day}.csv', sep=';'))
    trades_data.append(pd.read_csv(f'/Users/HP/src/prosperity4/algs/r4/trades_round_4_day_{day}.csv', sep=';'))

prices_df = pd.concat(prices_data, ignore_index=True)
trades_df = pd.concat(trades_data, ignore_index=True)

print("=" * 80)
print("EXPLORATORY DATA ANALYSIS - IMC PROSPERITY ROUND 4")
print("=" * 80)

# 1. DATASET OVERVIEW
print("\n1. DATASET OVERVIEW")
print(f"   Prices records: {len(prices_df):,}")
print(f"   Trades records: {len(trades_df):,}")
print(f"   Price columns: {prices_df.shape[1]}")
print(f"   Trade columns: {trades_df.shape[1]}")

# 2. PRODUCTS ANALYSIS
print("\n2. PRODUCTS ANALYSIS")
unique_products = prices_df['product'].unique()
print(f"   Total unique products: {len(unique_products)}")

# Separate algorithmic and manual products
algo_products = ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']
vev_products = [p for p in unique_products if p.startswith('VEV_')]
print(f"\n   Algorithmic Trading Products (3):")
print(f"   - HYDROGEL_PACK")
print(f"   - VELVETFRUIT_EXTRACT")
for i in range(1, 11):
    print(f"   - VELVETFRUIT_EXTRACT_VOUCHER (VEV_*)")
    break
print(f"\n   Voucher Products: {len(vev_products)} VEV contracts")
print(f"   Available VEV strikes: {sorted([int(p.split('_')[1]) for p in vev_products])}")

# 3. VOLUME & LIQUIDITY ANALYSIS
print("\n3. LIQUIDITY ANALYSIS (by product)")
for product in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT'] + sorted(vev_products)[:5]:
    if product in prices_df['product'].values:
        prod_data = prices_df[prices_df['product'] == product]
        avg_bid_vol = prod_data['bid_volume_1'].mean()
        avg_ask_vol = prod_data['ask_volume_1'].mean()
        spread = (prod_data['ask_price_1'] - prod_data['bid_price_1']).mean()
        print(f"   {product:30s} | Bid Vol: {avg_bid_vol:6.1f} | Ask Vol: {avg_ask_vol:6.1f} | Avg Spread: {spread:6.2f}")

# 4. PRICE STATISTICS
print("\n4. PRICE STATISTICS (Core Algorithmic Products)")
for product in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
    prod_data = prices_df[prices_df['product'] == product]
    print(f"\n   {product}:")
    print(f"      Mid price range: {prod_data['mid_price'].min():.1f} - {prod_data['mid_price'].max():.1f}")
    print(f"      Avg mid price:   {prod_data['mid_price'].mean():.2f}")
    print(f"      Std deviation:   {prod_data['mid_price'].std():.2f}")
    print(f"      Price swings:    {(prod_data['mid_price'].max() - prod_data['mid_price'].min()):.1f}")

# 5. COUNTERPARTY ANALYSIS
print("\n5. COUNTERPARTY BEHAVIOR ANALYSIS")
counterparties = set(trades_df['buyer'].unique()) | set(trades_df['seller'].unique())
print(f"   Total counterparties: {len(counterparties)}")

counterparty_stats = defaultdict(lambda: {'buy_count': 0, 'sell_count': 0, 'buy_volume': 0, 'sell_volume': 0, 'products': set()})

for _, trade in trades_df.iterrows():
    buyer = trade['buyer']
    seller = trade['seller']
    symbol = trade['symbol']
    qty = trade['quantity']
    
    counterparty_stats[buyer]['buy_count'] += 1
    counterparty_stats[buyer]['buy_volume'] += qty
    counterparty_stats[buyer]['products'].add(symbol)
    
    counterparty_stats[seller]['sell_count'] += 1
    counterparty_stats[seller]['sell_volume'] += qty
    counterparty_stats[seller]['products'].add(symbol)

print("\n   Top 10 Counterparties by Activity:")
print(f"   {'Counterparty':<15} {'Buys':>6} {'Sells':>6} {'Buy Vol':>8} {'Sell Vol':>8} {'Net Position':>12}")
print(f"   {'-'*65}")

sorted_counterparties = sorted(counterparty_stats.items(), 
                               key=lambda x: (x[1]['buy_count'] + x[1]['sell_count']), 
                               reverse=True)[:10]

for name, stats in sorted_counterparties:
    net_pos = stats['buy_volume'] - stats['sell_volume']
    print(f"   {name:<15} {stats['buy_count']:>6} {stats['sell_count']:>6} {stats['buy_volume']:>8} {stats['sell_volume']:>8} {net_pos:>12}")

# 6. TRADING PATTERN ANALYSIS
print("\n6. TRADING PATTERN ANALYSIS")
print("\n   Products by Counterparty Type:")

# Identify trader types
mark_01_trades = trades_df[(trades_df['buyer'] == 'Mark 01') | (trades_df['seller'] == 'Mark 01')]
mark_22_trades = trades_df[(trades_df['buyer'] == 'Mark 22') | (trades_df['seller'] == 'Mark 22')]

print(f"\n   Mark 01 (Potential Market Maker):")
print(f"      Total trades: {len(mark_01_trades)}")
print(f"      Products traded: {mark_01_trades['symbol'].nunique()}")
print(f"      Main products: {mark_01_trades['symbol'].value_counts().head(3).index.tolist()}")

print(f"\n   Mark 22 (Counter-party):")
print(f"      Total trades: {len(mark_22_trades)}")
print(f"      Products traded: {mark_22_trades['symbol'].nunique()}")
print(f"      Main products: {mark_22_trades['symbol'].value_counts().head(3).index.tolist()}")

# 7. SPREAD & ARBITRAGE OPPORTUNITIES
print("\n7. SPREAD ANALYSIS (Algorithmic Products)")
for product in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
    prod_data = prices_df[prices_df['product'] == product]
    spreads = prod_data['ask_price_1'] - prod_data['bid_price_1']
    print(f"\n   {product}:")
    print(f"      Min spread: {spreads.min():.1f}")
    print(f"      Max spread: {spreads.max():.1f}")
    print(f"      Avg spread: {spreads.mean():.2f}")
    print(f"      % spread:   {(spreads.mean() / prod_data['mid_price'].mean() * 100):.3f}%")

# 8. VOUCHER RELATIONSHIPS
print("\n8. VELVETFRUIT EXTRACT VOUCHER (VEV) ANALYSIS")
vev_trades = trades_df[trades_df['symbol'].str.startswith('VEV_')]
vev_info = defaultdict(lambda: {'volume': 0, 'price_range': [], 'trades': 0})

for _, trade in vev_trades.iterrows():
    symbol = trade['symbol']
    vev_info[symbol]['volume'] += trade['quantity']
    vev_info[symbol]['price_range'].append(trade['price'])
    vev_info[symbol]['trades'] += 1

print("\n   VEV Strike Activity (Top 5):")
print(f"   {'Strike':<10} {'Trades':>8} {'Volume':>8} {'Avg Price':>12} {'Price Range':>20}")
print(f"   {'-'*60}")

sorted_vevs = sorted(vev_info.items(), key=lambda x: x[1]['volume'], reverse=True)[:5]
for strike, info in sorted_vevs:
    if info['price_range']:
        avg_price = np.mean(info['price_range'])
        price_min, price_max = min(info['price_range']), max(info['price_range'])
        print(f"   {strike:<10} {info['trades']:>8} {info['volume']:>8} {avg_price:>12.1f} {price_min:>10.1f} - {price_max:>8.1f}")

print("\n" + "=" * 80)