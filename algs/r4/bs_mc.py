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

# ----------------------------
# Black-Scholes
# ----------------------------
def black_scholes(S, K, T, r, sigma, option_type="call"):
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)

    vol_sqrtT = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_sqrtT
    d2 = d1 - vol_sqrtT

    if option_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

# ----------------------------
# GBM Simulation
# ----------------------------
def simulate_gbm_paths(S0, sigma, n_steps, n_sims=100000, seed=42):
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n_sims, n_steps))

    drift = (-0.5 * sigma**2) * DT
    diffusion = sigma * math.sqrt(DT) * Z

    log_paths = np.cumsum(drift + diffusion, axis=1)
    S = S0 * np.exp(log_paths)

    return np.column_stack([np.full(n_sims, S0), S])

# ----------------------------
# Payoffs
# ----------------------------
def payoff_binary_put(ST, K, cash=10.0):
    return np.where(ST < K, cash, 0.0)

def payoff_chooser(S_14, K):
    return np.maximum(np.maximum(S_14 - K, 0.0), np.maximum(K - S_14, 0.0))

def payoff_knockout_put(path_min, ST, K, barrier):
    alive = path_min >= barrier
    return np.where(alive, np.maximum(K - ST, 0.0), 0.0)

# ----------------------------
# Main model
# ----------------------------
def build_table(S0=50.0, sigma=2.51, r=0.0, n_sims=100000, seed=42):

    rows = [
        {"product": "AC",        "bid": 49.975, "ask": 50.025, "kind": "underlying", "K": None, "Tw": None},
        {"product": "AC_50_P",   "bid": 12.000, "ask": 12.050, "kind": "put", "K": 50, "Tw": 3},
        {"product": "AC_50_C",   "bid": 12.000, "ask": 12.050, "kind": "call", "K": 50, "Tw": 3},
        {"product": "AC_35_P",   "bid": 4.330,  "ask": 4.350,  "kind": "put", "K": 35, "Tw": 3},
        {"product": "AC_40_P",   "bid": 6.500,  "ask": 6.550,  "kind": "put", "K": 40, "Tw": 3},
        {"product": "AC_45_P",   "bid": 9.050,  "ask": 9.100,  "kind": "put", "K": 45, "Tw": 3},
        {"product": "AC_60_C",   "bid": 8.800,  "ask": 8.850,  "kind": "call", "K": 60, "Tw": 3},
        {"product": "AC_50_P_2", "bid": 9.700,  "ask": 9.750,  "kind": "put", "K": 50, "Tw": 2},
        {"product": "AC_50_C_2", "bid": 9.700,  "ask": 9.750,  "kind": "call", "K": 50, "Tw": 2},
        {"product": "AC_50_CO",  "bid": 22.200, "ask": 22.300, "kind": "chooser", "K": 50, "Tw": 3},
        {"product": "AC_40_BP",  "bid": 5.000,  "ask": 5.100,  "kind": "binary_put", "K": 40, "Tw": 3},
        {"product": "AC_45_KO",  "bid": 0.150,  "ask": 0.175,  "kind": "knockout", "K": 45, "Tw": 3},
    ]

    n3w = steps_for_weeks(3)
    n2w = steps_for_weeks(2)

    paths = simulate_gbm_paths(S0, sigma, n3w, n_sims=n_sims, seed=seed)

    ST_3w = paths[:, -1]
    ST_2w = paths[:, n2w]
    path_min = paths.min(axis=1)

    out = []

    for r0 in rows:
        K = r0["K"]
        Tw = r0["Tw"]

        kind = r0["kind"]

        if kind == "underlying":
            model = float(ST_3w.mean())

        elif kind == "call":
            model = black_scholes(S0, K, weeks_to_years(Tw), r, sigma, "call")

        elif kind == "put":
            model = black_scholes(S0, K, weeks_to_years(Tw), r, sigma, "put")

        elif kind == "chooser":
            model = float(payoff_chooser(ST_2w, K).mean())

        elif kind == "binary_put":
            model = float(payoff_binary_put(ST_3w, K).mean())

        elif kind == "knockout":
            model = float(payoff_knockout_put(path_min, ST_3w, K, barrier=35).mean())

        else:
            model = np.nan

        mid = (r0["bid"] + r0["ask"]) / 2
        edge = model - mid

        side = "BUY" if model > r0["ask"] else "SELL" if model < r0["bid"] else "HOLD"

        out.append({
            "product": r0["product"],
            "bid": r0["bid"],
            "ask": r0["ask"],
            "mid": mid,
            "model_value": model,
            "edge_vs_mid": edge,
            "recommended_side": side,
        })

    return pd.DataFrame(out).sort_values("edge_vs_mid", ascending=False).reset_index(drop=True)

# ----------------------------
# Run
# ----------------------------
df = build_table()
print(df.to_string(index=False))