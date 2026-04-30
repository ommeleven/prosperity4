import numpy as np
from scipy.stats import norm

# Constants from the challenge
S0 = 50.0  # Midpoint of AC bid/ask
VOL = 2.51  # 251% annualized volatility
R = 0.0     # Zero risk-neutral drift
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
CONTRACT_SIZE = 3000
SIMULATIONS = 100000 # High count for convergence

def weeks_to_years(weeks):
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def get_steps(weeks):
    return int(round(weeks * 5 * STEPS_PER_DAY))

# --- Black-Scholes Formula (For Vanillas) ---
def black_scholes(S, K, T, r, sigma, kind="call"):
    if T <= 0: return max(0, S - K) if kind == "call" else max(0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if kind == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# --- Monte Carlo Engine ---
def run_monte_carlo(rows):
    # Max weeks determines the total simulation length
    max_weeks = 3 
    dt = 1 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
    total_steps = get_steps(max_weeks)
    
    # Generate GBM paths: S_t = S_{t-1} * exp((r - 0.5*sigma^2)dt + sigma*sqrt(dt)*Z)
    nudt = (R - 0.5 * VOL**2) * dt
    vsqdt = VOL * np.sqrt(dt)
    z = np.random.normal(0, 1, (SIMULATIONS, total_steps))
    path_returns = np.exp(nudt + vsqdt * z)
    paths = np.cumprod(path_returns, axis=1)
    paths = np.hstack([np.ones((SIMULATIONS, 1)), paths]) * S0

    results = []

    for row in rows:
        product = row["product"]
        kind = row["kind"]
        K = row["K"]
        Tw = row["Tw"]
        bid = row["bid"]
        ask = row["ask"]
        mid = (bid + ask) / 2
        
        steps_T = get_steps(Tw) if Tw else 0
        
        # Calculate Payoffs per Path
        if kind == "underlying":
            # Underlying fair value in risk-neutral is S0
            model_val = S0
        elif kind == "call":
            payoffs = np.maximum(paths[:, steps_T] - K, 0)
            model_val = np.mean(payoffs)
        elif kind == "put":
            payoffs = np.maximum(K - paths[:, steps_T], 0)
            model_val = np.mean(payoffs)
        elif kind == "chooser":
            # 3 weeks total, choose at 2 weeks (14 days)
            t_decision = get_steps(2)
            t_expiry = get_steps(3)
            # Logic: At 2 weeks, pick Call or Put based on which is ITM
            # Call payoff: S_3w - K; Put payoff: K - S_3w
            payoffs = []
            for i in range(SIMULATIONS):
                if paths[i, t_decision] > K: # Converts to Call
                    payoffs.append(max(paths[i, t_expiry] - K, 0))
                else: # Converts to Put
                    payoffs.append(max(K - paths[i, t_expiry], 0))
            model_val = np.mean(payoffs)
        elif kind == "binary_put":
            # Pays 10 if S_T < K
            payoffs = np.where(paths[:, steps_T] < K, 10, 0)
            model_val = np.mean(payoffs)
        elif kind == "knockout":
            # Put with K=45, Barrier=35. Path-dependent.
            barrier = 35
            # Check if any step up to expiry hit <= 35
            knocked_out = np.any(paths[:, :steps_T+1] < barrier, axis=1)
            standard_put = np.maximum(K - paths[:, steps_T], 0)
            payoffs = np.where(knocked_out, 0, standard_put)
            model_val = np.mean(payoffs)
        
        edge = model_val - ask if model_val > ask else (bid - model_val if model_val < bid else 0)
        side = "BUY" if model_val > ask else ("SELL" if model_val < bid else "NEUTRAL")
        
        results.append({
            "product": product,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "model_value": round(model_val, 4),
            "edge_vs_mkt": round(model_val - mid, 4),
            "recommended_side": side
        })
    
    return results

# Data input
rows = [
    {"product": "AC",        "bid": 49.975, "ask": 50.025, "kind": "underlying", "K": None, "Tw": None},
    {"product": "AC_50_P",   "bid": 12.000,  "ask": 12.050,  "kind": "put",       "K": 50,   "Tw": 3},
    {"product": "AC_50_C",   "bid": 12.000,  "ask": 12.050,  "kind": "call",      "K": 50,   "Tw": 3},
    {"product": "AC_35_P",   "bid": 4.330,   "ask": 4.350,   "kind": "put",       "K": 35,   "Tw": 3},
    {"product": "AC_40_P",   "bid": 6.500,   "ask": 6.550,   "kind": "put",       "K": 40,   "Tw": 3},
    {"product": "AC_45_P",   "bid": 9.050,   "ask": 9.100,   "kind": "put",       "K": 45,   "Tw": 3},
    {"product": "AC_60_C",   "bid": 8.800,   "ask": 8.850,   "kind": "call",      "K": 60,   "Tw": 3},
    {"product": "AC_50_P_2", "bid": 9.700,   "ask": 9.750,   "kind": "put",       "K": 50,   "Tw": 2},
    {"product": "AC_50_C_2", "bid": 9.700,   "ask": 9.750,   "kind": "call",      "K": 50,   "Tw": 2},
    {"product": "AC_50_CO",  "bid": 22.200,  "ask": 22.300,  "kind": "chooser",   "K": 50,   "Tw": 3},
    {"product": "AC_40_BP",  "bid": 5.000,   "ask": 5.100,   "kind": "binary_put","K": 40,   "Tw": 3},
    {"product": "AC_45_KO",  "bid": 0.150,   "ask": 0.175,   "kind": "knockout",  "K": 45,   "Tw": 3},
]

output = run_monte_carlo(rows)

# Print Table
print(f"{'Product':<12} | {'Mid':<8} | {'Model':<10} | {'Edge':<10} | {'Side':<8}")
print("-" * 60)
for res in output:
    print(f"{res['product']:<12} | {res['mid']:<8.3f} | {res['model_value']:<10.4f} | {res['edge_vs_mkt']:<10.4f} | {res['recommended_side']:<8}")