import pandas as pd
import numpy as np
import glob

# =========================
# LOAD DATA
# =========================
def load_data(price_path_pattern, trade_path_pattern):
    price_files = sorted(glob.glob(price_path_pattern))
    trade_files = sorted(glob.glob(trade_path_pattern))

    prices = pd.concat([pd.read_csv(f) for f in price_files])
    trades = pd.concat([pd.read_csv(f) for f in trade_files])

    return prices, trades


# =========================
# BASIC FEATURES
# =========================
def find_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"None of these columns found: {candidates}")


def compute_basic_features(prices):
    df = prices.copy()

    # Detect correct column names dynamically
    bid_col = find_column(df, [
        'bid_price_1', 'bid_price_0', 'bid_price', 'best_bid'
    ])

    ask_col = find_column(df, [
        'ask_price_1', 'ask_price_0', 'ask_price', 'best_ask'
    ])

    bid_vol_col = find_column(df, [
        'bid_volume_1', 'bid_volume_0', 'bid_volume'
    ])

    ask_vol_col = find_column(df, [
        'ask_volume_1', 'ask_volume_0', 'ask_volume'
    ])

    # Compute features
    df['mid'] = (df[bid_col] + df[ask_col]) / 2
    df['spread'] = df[ask_col] - df[bid_col]

    df['imbalance'] = (
        df[bid_vol_col] - df[ask_vol_col]
    ) / (df[bid_vol_col] + df[ask_vol_col] + 1e-9)
    
    return df


# =========================
# ORDER FLOW
# =========================
def compute_order_flow(trades):
    df = trades.copy()

    # Try common schemas
    if 'buyer' in df.columns and 'seller' in df.columns:
        df['signed_volume'] = np.where(
            df['buyer'] == "SUBMISSION",
            df['quantity'],
            -df['quantity']
        )

    elif 'side' in df.columns:
        df['signed_volume'] = np.where(
            df['side'] == 'BUY',
            df['quantity'],
            -df['quantity']
        )

    else:
        # fallback: assume all trades are unsigned
        df['signed_volume'] = df['quantity']

    df['order_flow'] = df['signed_volume'].rolling(50).sum()

    return df


# =========================
# PRICE IMPACT
# =========================
def compute_price_impact(prices, trades):
    prices = prices.copy()
    trades = trades.copy()

    print(prices.head())
    print(trades.head())

    prices['mid'] = (prices['bid_price_1'] + prices['ask_price_1']) / 2

    # Align trades to nearest price timestamp
    merged = pd.merge_asof(
        trades.sort_values('timestamp'),
        prices[['timestamp', 'mid']].sort_values('timestamp'),
        on='timestamp'
    )

    # Future mid price (lag)
    merged['future_mid'] = merged['mid'].shift(-10)

    # Impact = future move after trade
    merged['impact'] = merged['future_mid'] - merged['mid']

    return merged


# =========================
# SIGNAL DISCOVERY
# =========================
def analyze_signals(prices, trades):
    results = {}

    # --- Imbalance vs Returns ---
    prices['future_return'] = prices['mid'].shift(-10) - prices['mid']
    corr_imb = prices[['imbalance', 'future_return']].corr().iloc[0, 1]

    results['imbalance_alpha'] = corr_imb

    # --- Order flow vs Returns ---
    merged = pd.merge_asof(
        trades.sort_values('timestamp'),
        prices[['timestamp', 'mid']].sort_values('timestamp'),
        on='timestamp'
    )

    merged['future_return'] = merged['mid'].shift(-10) - merged['mid']
    corr_flow = merged[['signed_volume', 'future_return']].corr().iloc[0, 1]

    results['orderflow_alpha'] = corr_flow

    return results


# =========================
# MARKET REGIME DETECTION
# =========================
def detect_regime(prices):
    avg_spread = prices['spread'].mean()
    spread_vol = prices['spread'].std()

    if avg_spread < 1:
        regime = "HIGHLY COMPETITIVE MM"
    elif spread_vol > 2:
        regime = "VOLATILE / TOXIC FLOW"
    else:
        regime = "NORMAL"

    return regime


# =========================
# MAIN PIPELINE
# =========================
def run_analysis():
    prices, trades = load_data(
        "prices_round_3_day_*.csv",
        "trades_round_3_day_*.csv"
    )

    prices = compute_basic_features(prices)
    trades = compute_order_flow(trades)

    impact = compute_price_impact(prices, trades)
    signals = analyze_signals(prices, trades)
    regime = detect_regime(prices)

    print("\n=== MARKET MICROSTRUCTURE REPORT ===\n")

    print(f"Regime: {regime}")
    print(f"Avg Spread: {prices['spread'].mean():.4f}")
    print(f"Imbalance Alpha: {signals['imbalance_alpha']:.4f}")
    print(f"Order Flow Alpha: {signals['orderflow_alpha']:.4f}")
    print(f"Avg Trade Impact: {impact['impact'].mean():.4f}")

    print("\n=== EXPLOITABLE PATTERNS ===\n")

    if signals['imbalance_alpha'] > 0.02:
        print("→ Use IMBALANCE-BASED MARKET MAKING")

    if signals['orderflow_alpha'] > 0.02:
        print("→ Use ORDER FLOW MOMENTUM")

    if impact['impact'].mean() > 0:
        print("→ Trades move price → follow aggressive flow")

    if impact['impact'].mean() < 0:
        print("→ Mean reversion after trades → fade flow")


if __name__ == "__main__":
    run_analysis()