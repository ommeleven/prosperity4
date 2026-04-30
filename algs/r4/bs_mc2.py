import numpy as np
import pandas as pd
import math

# ----------------------------
# CONFIG
# ----------------------------
R = 0.0
SIGMA = 0.20
S0 = 50.0
N_SIM = 100_000

TRADING_DAYS_PER_YEAR = 252

# ----------------------------
# TIME CONVERSION
# ----------------------------
def weeks_to_years(days):
    return days / TRADING_DAYS_PER_YEAR

def parse_t(expiry_str):
    if expiry_str is None:
        return 0.0

    if "N/A" in str(expiry_str):
        return 0.0  # spot / underlying

    cleaned = str(expiry_str).replace("T+", "")

    if "/" in cleaned:
        parts = cleaned.split("/")
        days = np.mean([float(p) for p in parts])
    else:
        days = float(cleaned)

    return days / TRADING_DAYS_PER_YEAR

# ----------------------------
# BLACK-SCHOLES
# ----------------------------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs_price(S, K, T, sigma, option_type):
    T = float(T)   
    if T <= 0:
        return max(S - K, 0) if option_type == "call" else max(K - S, 0)

    d1 = (math.log(S / K) + (0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm_cdf(d1) - K * norm_cdf(d2)
    else:
        return K * norm_cdf(-d2) - S * norm_cdf(-d1)


# ----------------------------
# MONTE CARLO
# ----------------------------
def monte_carlo_price(S, K, T, sigma, payoff_fn):
    Z = np.random.randn(N_SIM)
    ST = S * np.exp((-0.5 * sigma**2) * T + sigma * np.sqrt(T) * Z)
    return np.mean(payoff_fn(ST))


# ----------------------------
# RAW MARKET DATA (CLEANED)
# ----------------------------
raw_data = [
    ("AC",        "N/A",        50,   49.975, 50.025, "spot"),

    ("AC_50_P",   "T+21",       50,   12.00,  12.05,  "put"),
    ("AC_50_C",   "T+21",       50,   12.00,  12.05,  "call"),

    ("AC_35_P",   "T+21",       35,   4.33,   4.35,   "put"),
    ("AC_40_P",   "T+21",       40,   6.50,   6.55,   "put"),
    ("AC_45_P",   "T+21",       45,   9.05,   9.10,   "put"),
    ("AC_60_C",   "T+21",       60,   8.80,   8.85,   "call"),

    ("AC_50_P_2", "T+14",       50,   9.70,   9.75,   "put"),
    ("AC_50_C_2", "T+14",       50,   9.70,   9.75,   "call"),

    ("AC_50_CO",  "T+14/21",    50,   22.20,  22.30,  "chooser"),

    ("AC_40_BP",  "T+21",       40,   5.00,   5.10,   "binary_put"),
    ("AC_45_KO",  "T+21",       45,   0.15,   0.175,  "knockout"),
]

df = pd.DataFrame(raw_data, columns=["name", "expiry", "K", "bid", "ask", "type"])
df["T"] = df["expiry"].apply(parse_t)
df["T"] = pd.to_numeric(df["T"], errors="coerce").fillna(0.0)

# ----------------------------
# PAYOFFS
# ----------------------------
def payoff_call(ST, K):
    return np.maximum(ST - K, 0)

def payoff_put(ST, K):
    return np.maximum(K - ST, 0)

def payoff_binary_put(ST, K, payout=10):
    return np.where(ST < K, payout, 0)

def payoff_chooser(ST, K):
    return np.maximum(np.maximum(ST - K, 0), np.maximum(K - ST, 0))


# ----------------------------
# PRICING ENGINE
# ----------------------------
results = []
for row in df.itertuples(index=False):

    mid = (row.bid + row.ask) / 2

    if row.type == "spot":
        model = S0

    elif row.type == "call":
        bs = bs_price(S0, row.K, row.T, SIGMA, "call")
        mc = monte_carlo_price(S0, row.K, row.T, SIGMA,
                                lambda ST: np.maximum(ST - row.K, 0))
        model = 0.5 * (bs + mc)

    elif row.type == "put":
        bs = bs_price(S0, row.K, row.T, SIGMA, "put")
        mc = monte_carlo_price(S0, row.K, row.T, SIGMA,
                                lambda ST: np.maximum(row.K - ST, 0))
        model = 0.5 * (bs + mc)

    elif row.type == "chooser":
        model = monte_carlo_price(S0, row.K, row.T, SIGMA,
                                  lambda ST: np.abs(ST - row.K)).mean()

    elif row.type == "binary_put":
        model = monte_carlo_price(S0, row.K, row.T, SIGMA,
                                  lambda ST: np.where(ST < row.K, 10, 0)).mean()

    else:
        model = np.nan
        
    results.append({
        "name": row.name,
        "expiry": row.expiry,
        "K": row.K,
        "mid": mid,
        "model": model,
        "edge": model - mid,
        "signal": "BUY" if model > row.ask else "SELL" if model < row.bid else "HOLD"
    })


# ----------------------------
# OUTPUT
# ----------------------------
res_df = pd.DataFrame(results)
res_df = res_df.sort_values("edge", ascending=False)

print("\n=== INTARIAN OPTION EDGE TABLE ===\n")
print(res_df.to_string(index=False))