import numpy as np
import pandas as pd
import glob
import itertools

# =========================
# LOAD ALL FILES
# =========================

price_files = sorted(glob.glob("prices_round_2_day_*.csv"))
trade_files = sorted(glob.glob("trades_round_2_day_*.csv"))

prices = pd.concat([pd.read_csv(f) for f in price_files], ignore_index=True)
trades = pd.concat([pd.read_csv(f) for f in trade_files], ignore_index=True)

# =========================
# SIMPLE BASE PnL ESTIMATION
# =========================

def estimate_base_pnl(prices, trades):
    pnl = 0
    
    # naive: assume we trade at mid and track price changes
    for product in prices['product'].unique():
        df = prices[prices['product'] == product].copy()
        
        if 'bid_price_1' in df.columns and 'ask_price_1' in df.columns:
            df['mid'] = (df['bid_price_1'] + df['ask_price_1']) / 2
        else:
            continue
        
        # trend-based PnL proxy
        pnl += df['mid'].iloc[-1] - df['mid'].iloc[0]
    
    return pnl

base_pnl = estimate_base_pnl(prices, trades)

# normalize to something meaningful
base_pnl = max(1, abs(base_pnl))

print(f"Estimated Base PnL Signal: {base_pnl:.2f}")

# =========================
# FUNCTIONS
# =========================

def research(x):
    return 200_000 * np.log(1 + x) / np.log(101)

def scale(x):
    return 7 * (x / 100)

def compute_score(r_pct, s_pct, sp_pct, speed_mult, base_signal):
    r = research(r_pct)
    s = scale(s_pct)
    sp = speed_mult
    
    gross = r * s * sp * (base_signal / 10000)  # normalize
    budget = r_pct + s_pct + sp_pct
    
    return gross - budget

# =========================
# GRID SEARCH
# =========================

allocs = range(0, 101, 5)

results = []

for r, s, sp in itertools.product(allocs, allocs, allocs):
    if r + s + sp > 100:
        continue
    
    for label, speed_val in {
        "low": 0.3,
        "mid": 0.5,
        "high": 0.9
    }.items():
        
        score = compute_score(r, s, sp, speed_val, base_pnl)
        
        results.append({
            "research": r,
            "scale": s,
            "speed": sp,
            "speed_case": label,
            "score": score
        })

df = pd.DataFrame(results)

best = df.sort_values("score", ascending=False).head(10)

print("\n🔥 BEST ALLOCATIONS:\n")
print(best)