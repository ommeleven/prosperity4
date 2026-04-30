import math
import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY
DT = 1 / STEPS_PER_YEAR

# ----------------------------
# Utilities
# ----------------------------
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def weeks_to_years(weeks):
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def steps_for_weeks(weeks):
    return int(round(weeks * 5 * STEPS_PER_DAY))

def black_scholes(S, K, T, r, sigma, option_type="call"):
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

def simulate_gbm_paths(S0, sigma, n_steps, n_sims=100000, seed=42):
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n_sims, n_steps))
    increments = (-0.5 * sigma**2) * DT + sigma * math.sqrt(DT) * Z
    log_paths = np.cumsum(increments, axis=1)
    S = S0 * np.exp(log_paths)
    return np.column_stack([np.full(n_sims, S0), S])

# ----------------------------
# Payoff functions
# ----------------------------
def payoff_binary_put(ST, K, cash=10.0):
    return np.where(ST < K, cash, 0.0)

def payoff_knockout_put(path_min, ST, K, barrier):
    alive = path_min >= barrier
    return np.where(alive, np.maximum(K - ST, 0.0), 0.0)

# ----------------------------
# Main table builder
# ----------------------------
def build_table(
    S0=50.0,
    sigma=2.51,
    r=0.0,
    n_sims=100000,
    seed=42,
    buffer=0.0,   # trading buffer to avoid noise
):
    rows = [
        {"product": "AC",        "bid": 49.975, "ask": 50.025, "kind": "underlying", "K": None, "Tw": None},
        {"product": "AC_50_P",   "bid": 12.000,  "ask": 12.050, "kind": "put",       "K": 50,   "Tw": 3},
        {"product": "AC_50_C",   "bid": 12.000,  "ask": 12.050, "kind": "call",      "K": 50,   "Tw": 3},
        {"product": "AC_35_P",   "bid": 4.330,   "ask": 4.350,  "kind": "put",       "K": 35,   "Tw": 3},
        {"product": "AC_40_P",   "bid": 6.500,   "ask": 6.550,  "kind": "put",       "K": 40,   "Tw": 3},
        {"product": "AC_45_P",   "bid": 9.050,   "ask": 9.100,  "kind": "put",       "K": 45,   "Tw": 3},
        {"product": "AC_60_C",   "bid": 8.800,   "ask": 8.850,  "kind": "call",      "K": 60,   "Tw": 3},
        {"product": "AC_50_P_2", "bid": 9.700,   "ask": 9.750,  "kind": "put",       "K": 50,   "Tw": 2},
        {"product": "AC_50_C_2", "bid": 9.700,   "ask": 9.750,  "kind": "call",      "K": 50,   "Tw": 2},
        {"product": "AC_50_CO",  "bid": 22.200,  "ask": 22.300, "kind": "chooser",   "K": 50,   "Tw": 3},
        {"product": "AC_40_BP",  "bid": 5.000,   "ask": 5.100,  "kind": "binary_put","K": 40,   "Tw": 3},
        {"product": "AC_45_KO",  "bid": 0.150,   "ask": 0.175,  "kind": "knockout",  "K": 45,   "Tw": 3},
    ]

    n21 = steps_for_weeks(3)
    n14 = steps_for_weeks(2)

    paths21 = simulate_gbm_paths(S0, sigma, n21, n_sims=n_sims, seed=seed)
    ST_21 = paths21[:, -1]
    ST_14 = paths21[:, n14]
    path_min_21 = paths21.min(axis=1)

    out = []

    for row in rows:
        product = row["product"]
        bid = row["bid"]
        ask = row["ask"]
        kind = row["kind"]
        K = row["K"]
        Tw = row["Tw"]

        if kind == "underlying":
            model = S0 * math.exp(r * weeks_to_years(3))  # exact expectation

        elif kind == "call":
            T = weeks_to_years(Tw)
            model = black_scholes(S0, K, T, r, sigma, "call")

        elif kind == "put":
            T = weeks_to_years(Tw)
            model = black_scholes(S0, K, T, r, sigma, "put")

        elif kind == "chooser":
            T_total = weeks_to_years(Tw)
            T_decision = weeks_to_years(2)
            T_remaining = T_total - T_decision

            # continuation values
            C = np.array([black_scholes(s, K, T_remaining, r, sigma, "call") for s in ST_14])
            P = np.array([black_scholes(s, K, T_remaining, r, sigma, "put") for s in ST_14])
            payoff = np.maximum(C, P)

            model = math.exp(-r * T_decision) * payoff.mean()

        elif kind == "binary_put":
            T = weeks_to_years(Tw)
            payoff = payoff_binary_put(ST_21, K, cash=10.0)
            model = math.exp(-r * T) * payoff.mean()

        elif kind == "knockout":
            T = weeks_to_years(Tw)
            payoff = payoff_knockout_put(path_min_21, ST_21, K, barrier=35)
            model = math.exp(-r * T) * payoff.mean()

        else:
            model = np.nan

        mid = 0.5 * (bid + ask)
        edge_mid = model - mid

        if model > ask + buffer:
            side = "BUY"
        elif model < bid - buffer:
            side = "SELL"
        else:
            side = "HOLD"

        out.append({
            "product": product,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "model_value": model,
            "edge_vs_mid": edge_mid,
            "recommended_side": side,
        })

    df = pd.DataFrame(out)
    return df.sort_values("edge_vs_mid", ascending=False).reset_index(drop=True)

# ----------------------------
# Run
# ----------------------------
df = build_table(S0=50.0, sigma=2.51, r=0.0, n_sims=100000, seed=42, buffer=0.05)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
print(df.to_string(index=False))