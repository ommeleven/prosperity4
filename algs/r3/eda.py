import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import norm
import os

# ------------------------------
# 1. Load data
# ------------------------------

def load_prices(filepath):
    """Load prices CSV file."""
    df = pd.read_csv(filepath, sep=';')
    # Convert timestamp to int if needed
    df['timestamp'] = df['timestamp'].astype(int)
    return df

def load_trades(filepath):
    """Load trades CSV file."""
    df = pd.read_csv(filepath, sep=';')
    df['timestamp'] = df['timestamp'].astype(int)
    # Some rows may have empty buyer/seller; fill with 'market'
    df['buyer'] = df['buyer'].fillna('market')
    df['seller'] = df['seller'].fillna('market')
    return df

# List of days
days = [0, 1, 2]
prices_dfs = {}
trades_dfs = {}

prices_list = []
trades_list = []
for day in days:
    prices_df = load_prices(f'prices_round_3_day_{day}.csv')
    trades_df = load_trades(f'trades_round_3_day_{day}.csv')
    prices_list.append(prices_df)
    trades_list.append(trades_df)

prices_all = pd.concat(prices_list, ignore_index=True)
trades_all = pd.concat(trades_list, ignore_index=True)

# ------------------------------
# 2. Understand the products
# ------------------------------

products = prices_all['product'].unique()
print("Available products:")
for p in products:
    print(f"  - {p}")

# ------------------------------
# 3. Underlying price dynamics (VELVETFRUIT_EXTRACT and HYDROGEL_PACK)
# ------------------------------

underlyings = ['VELVETFRUIT_EXTRACT', 'HYDROGEL_PACK']

fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(12, 8))
for i, prod in enumerate(underlyings):
    prod_data = prices_all[prices_all['product'] == prod].copy()
    # Use mid price as representative
    ax = axes[i]
    for day in days:
        day_data = prod_data[prod_data['day'] == day]
        ax.plot(day_data['timestamp'], day_data['mid_price'], label=f'Day {day}')
    ax.set_title(f'{prod} mid price over time')
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price')
    ax.legend()
    ax.grid(True)
plt.tight_layout()
plt.show()

# Calculate returns and volatility
for prod in underlyings:
    prod_data = prices_all[prices_all['product'] == prod].sort_values(['day', 'timestamp'])
    prod_data['returns'] = prod_data['mid_price'].pct_change()
    # Volatility (annualised  - assuming 100 iterations per day? Actually we don't know freq, just compare)
    daily_vol = prod_data.groupby('day')['returns'].std()
    print(f"\n{prod} daily return std (by day):\n{daily_vol}")

# ------------------------------
# 4. Bid-ask spread analysis
# ------------------------------

def compute_spread(row):
    """Compute bid-ask spread using best bid and best ask."""
    # Best bid is bid_price_1 (if exists)
    best_bid = row['bid_price_1'] if pd.notna(row['bid_price_1']) else np.nan
    best_ask = row['ask_price_1'] if pd.notna(row['ask_price_1']) else np.nan
    if pd.notna(best_bid) and pd.notna(best_ask):
        return best_ask - best_bid
    else:
        return np.nan

prices_all['spread'] = prices_all.apply(compute_spread, axis=1)

# Plot spread for underlyings
for prod in underlyings:
    prod_data = prices_all[prices_all['product'] == prod].copy()
    plt.figure(figsize=(10, 4))
    for day in days:
        day_data = prod_data[prod_data['day'] == day]
        plt.plot(day_data['timestamp'], day_data['spread'], label=f'Day {day}')
    plt.title(f'{prod} bid-ask spread')
    plt.xlabel('Timestamp')
    plt.ylabel('Spread')
    plt.legend()
    plt.grid(True)
    plt.show()

# ------------------------------
# 5. Option (voucher) pricing analysis
# ------------------------------

# Extract all voucher products (start with VEV_)
vouchers = [p for p in products if p.startswith('VEV_')]
# Get strikes from names
strike_map = {v: int(v.split('_')[1]) for v in vouchers}

# For each day, compute time to expiry in years (TTE at start of round: 7 days for round 1? But here we have days 0,1,2)
# According to description: round1 starts with TTE=7d, round2=6d, round3=5d. Historical days: day0 corresponds to tutorial? 
# But for EDA we can just use relative TTE = (7 - day) days? Actually round3 day1 is day1? We'll assume day0 of round3 has TTE=7, day1=6, day2=5.
# However prices files contain 'day' column: for day0 of round3, TTE=7? But the provided file shows day=1 for some data.
# Let's simplify: we'll just compare option prices to theoretical Black-Scholes using a guessed volatility (from underlying historical vol).

# We need underlying price for VELVETFRUIT_EXTRACT at each timestamp.
underlying_prices = prices_all[prices_all['product'] == 'VELVETFRUIT_EXTRACT'][['day', 'timestamp', 'mid_price']]
underlying_prices.rename(columns={'mid_price': 'S'}, inplace=True)

# Merge option prices with underlying
option_prices = prices_all[prices_all['product'].isin(vouchers)][['day', 'timestamp', 'product', 'mid_price']]
option_prices = option_prices.merge(underlying_prices, on=['day', 'timestamp'], how='left')

# Add strike
option_prices['strike'] = option_prices['product'].map(strike_map)

# Time to expiry in years (assume 1 day = 1/365 year, and TTE at day0 = 7 days)
option_prices['TTE_years'] = (7 - option_prices['day']) / 365.0

# Estimate historical volatility (annualised) from underlying returns
underlying_returns = underlying_prices.groupby('day')['S'].pct_change().dropna()
historical_vol = underlying_returns.std() * np.sqrt(365)  # annualised
print(f"\nEstimated underlying volatility (annual): {historical_vol:.3f}")

# Black-Scholes call price function
def bs_call(S, K, T, r, sigma):
    if T <= 0:
        return max(S - K, 0)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)

# Assume risk-free rate r=0 (simplification)
r = 0.0

# Compute theoretical price using historical vol
option_prices['theo_price'] = option_prices.apply(
    lambda row: bs_call(row['S'], row['strike'], row['TTE_years'], r, historical_vol), axis=1)

# Mispricing
option_prices['mispricing'] = option_prices['mid_price'] - option_prices['theo_price']

# Plot mispricing over time for a few strikes
strikes_to_plot = [4000, 5000, 6000]
fig, ax = plt.subplots(figsize=(12, 6))
for strike in strikes_to_plot:
    data = option_prices[option_prices['strike'] == strike]
    # Create a combined time index: day and timestamp
    data['time_idx'] = data['day'] * 100000 + data['timestamp']  # crude but works
    ax.plot(data['time_idx'], data['mispricing'], marker='o', linestyle='-', label=f'Strike {strike}')
ax.axhline(0, color='red', linestyle='--')
ax.set_title('Option mispricing (market - Black-Scholes)')
ax.set_xlabel('Day + timestamp')
ax.set_ylabel('Mispricing')
ax.legend()
plt.xticks(rotation=45)
plt.grid(True)
plt.show()

# ------------------------------
# 6. Volume analysis from trades
# ------------------------------

trades_all['quantity_abs'] = trades_all['quantity'].abs()
volume_by_product = trades_all.groupby(['day', 'symbol'])['quantity_abs'].sum().unstack()
print("\nTotal traded volume by product and day:")
print(volume_by_product)

# Plot trading volume over time
fig, ax = plt.subplots(figsize=(12, 5))
for prod in products:
    prod_trades = trades_all[trades_all['symbol'] == prod]
    # Aggregate volume per timestamp
    volume_ts = prod_trades.groupby(['day', 'timestamp'])['quantity_abs'].sum().reset_index()
    volume_ts['time_idx'] = volume_ts['day'] * 100000 + volume_ts['timestamp']
    ax.plot(volume_ts['time_idx'], volume_ts['quantity_abs'], label=prod, alpha=0.7)
ax.set_title('Trading volume over time')
ax.set_xlabel('Day+timestamp')
ax.set_ylabel('Volume')
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True)
plt.tight_layout()
plt.show()

# ------------------------------
# 7. Correlation matrix and heatmap
# ------------------------------

# Create a pivot of mid prices for all products at each timestamp
prices_pivot = prices_all.pivot_table(index=['day', 'timestamp'], columns='product', values='mid_price').reset_index()
# Drop columns that are all NaN
prices_pivot = prices_pivot.dropna(axis=1, how='all')
corr_matrix = prices_pivot.drop(['day', 'timestamp'], axis=1).corr()
plt.figure(figsize=(12, 10))
sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0)
plt.title('Correlation matrix of mid prices')
plt.show()

# ------------------------------
# 8. Summary insights and trading style suggestions
# ------------------------------

print("\n" + "="*60)
print("EDA SUMMARY AND TRADING STYLE SUGGESTIONS")
print("="*60)

# Check if options are systematically mispriced
mean_mispricing = option_prices.groupby('strike')['mispricing'].mean()
if (mean_mispricing.abs() > 20).any():
    print("- Options show consistent mispricing relative to Black-Scholes (using historical volatility).")
    print("  Potential strategy: **Volatility arbitrage** – sell overpriced options, buy underpriced ones.")
else:
    print("- Options appear fairly priced on average. Focus on delta-1 strategies.")

# Check spread tightness
avg_spread_underlying = prices_all[prices_all['product'].isin(underlyings)]['spread'].mean()
print(f"\n- Average bid-ask spread for underlyings: {avg_spread_underlying:.2f}")
if avg_spread_underlying < 5:
    print("  Spreads are tight → **Market making** can be profitable with low risk.")
else:
    print("  Spreads are wide → **Liquidity provision** (placing limit orders) may earn spread.")

# Check volume and opportunity
if volume_by_product.sum().sum() > 5000:
    print("\n- High trading volume suggests **directional strategies** can be executed without much slippage.")
else:
    print("\n- Low volume → be careful with large orders; use limit orders and avoid market orders.")

# Check if there are obvious arbitrage opportunities (e.g., put-call parity not applicable here, but we can look at the relation between vouchers and underlying)
# For example, a voucher with strike K should never trade above underlying price (S)
violations = option_prices[option_prices['mid_price'] > option_prices['S']].shape[0]
if violations > 0:
    print(f"\n- Found {violations} instances where an option price > underlying price (arbitrage).")
    print("  Strategy: **Risk-free arbitrage** – sell the option, buy the underlying (if allowed).")

print("\nRecommended trading styles based on this EDA:")
print("- If options are mispriced: volatility trading (calendar spreads, delta-hedging).")
print("- If spreads are wide: market making (capture bid-ask spread).")
print("- If trends exist in underlying: trend following or mean reversion (use returns analysis).")
print("- For manual Bio-Pod bidding: analyse the penalty formula and aim to set second bid above the average to avoid penalty.\n")