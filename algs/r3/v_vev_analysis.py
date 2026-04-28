import os
import pandas as pd
import numpy as np

folder = os.path.dirname(os.path.abspath(__file__))
files = [f for f in os.listdir(folder) if f.endswith(".csv")]
files.sort()

def compute_features(df):
    # Best bid/ask
    df["best_bid"] = df["bid_price_1"]
    df["best_ask"] = df["ask_price_1"]

    # Mid price
    df["mid"] = (df["best_bid"] + df["best_ask"]) / 2

    # Spread
    df["spread"] = df["best_ask"] - df["best_bid"]

    # Microprice (better fair value proxy)
    df["microprice"] = (
        df["best_bid"] * df["ask_volume_1"] +
        df["best_ask"] * df["bid_volume_1"]
    ) / (df["bid_volume_1"] + df["ask_volume_1"] + 1e-9)

    return df


def detect_mispricing(df):
    signals = {}

    # 1. Bid/Ask far from fair value
    df["bid_deviation"] = df["best_bid"] - df["microprice"]
    df["ask_deviation"] = df["best_ask"] - df["microprice"]

    signals["far_bid"] = df[df["bid_deviation"] < -df["spread"]]
    signals["far_ask"] = df[df["ask_deviation"] > df["spread"]]

    # 2. Wide spreads (inefficiency)
    spread_threshold = df["spread"].quantile(0.95)
    signals["wide_spread"] = df[df["spread"] > spread_threshold]

    # 3. Crossed / aggressive opportunities
    signals["crossed"] = df[df["best_bid"] >= df["best_ask"]]

    return signals


def aggressive_trade_conditions(df):
    conditions = []

    # Buy signal (ask cheap vs fair value)
    buy = df[df["best_ask"] < df["microprice"]]
    conditions.append(("BUY", buy))

    # Sell signal (bid expensive vs fair value)
    sell = df[df["best_bid"] > df["microprice"]]
    conditions.append(("SELL", sell))

    return conditions


def compute_time_value(df):
    """
    Assumes:
    - df has 'price' (option price)
    - df has 'strike'
    - df has 'underlying_price'
    """

    # Intrinsic value (call assumption)
    df["intrinsic"] = np.maximum(df["underlying_price"] - df["strike"], 0)

    # Time value
    df["time_value"] = df["price"] - df["intrinsic"]

    return df


def group_premium_by_strike(df):
    grouped = df.groupby("strike")["time_value"].mean()
    return grouped.to_dict()


# =========================
# RUN ANALYSIS
# =========================

all_data = []

for f in files:
    path = os.path.join(folder, f)
    try:
        df = pd.read_csv(path)
        df = compute_features(df)
        all_data.append(df)
    except Exception as e:
        print(f"Error in {f}: {e}")

df = pd.concat(all_data, ignore_index=True)

# ---- Mispricing ----
signals = detect_mispricing(df)

print("\n=== MISPRICING SIGNALS ===")
for k, v in signals.items():
    print(f"{k}: {len(v)} cases")

# ---- Aggressive trades ----
print("\n=== AGGRESSIVE TRADE OPPORTUNITIES ===")
for side, data in aggressive_trade_conditions(df):
    print(f"{side}: {len(data)} opportunities")

# ---- Time value (if options data exists) ----
if {"price", "strike", "underlying_price"}.issubset(df.columns):
    df = compute_time_value(df)
    mapping = group_premium_by_strike(df)

    print("\n=== TIME VALUE BY STRIKE ===")
    for strike, premium in mapping.items():
        print(f"Strike {strike}: Avg Premium = {premium:.4f}")
else:
    print("\n(No options data detected for time value analysis)")