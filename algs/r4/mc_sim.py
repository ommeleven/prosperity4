import numpy as np

# Parameters
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY
S0 = 50.0
R = 0.0
VOL = 2.51          # 251% annualised
CONTRACT_SIZE = 3000

# Time conversions
def weeks_to_steps(weeks):
    return int(round(weeks * 5 * STEPS_PER_DAY))

steps_2w = weeks_to_steps(2)   # 40 steps
steps_3w = weeks_to_steps(3)   # 60 steps

# Time per step (for 3-week simulation)
T_3w = (3 * 5) / TRADING_DAYS_PER_YEAR  # years
dt = T_3w / steps_3w

# Simulation
n_sim = 100_000
np.random.seed(42)

# Simulate full 3‑week paths (60 steps)
S = np.zeros((n_sim, steps_3w + 1))
S[:, 0] = S0
for i in range(steps_3w):
    Z = np.random.randn(n_sim)
    S[:, i+1] = S[:, i] * np.exp((R - 0.5*VOL**2) * dt + VOL * np.sqrt(dt) * Z)

# Extract prices at 2 weeks (step 40) and at expiry (step 60)
S_2w = S[:, steps_2w]
S_final = S[:, -1]

# Payoff functions
call_2w = np.maximum(S_2w - 50, 0)
put_2w = np.maximum(50 - S_2w, 0)

# Chooser payoff: at 2 weeks, choose call if S_2w > 50 else put
chooser_payoff = np.where(S_2w > 50,
                          np.maximum(S_final - 50, 0),
                          np.maximum(50 - S_final, 0))

# Binary put (strike 40, pays 10 if S_final < 40)
binary_payoff = 10.0 * (S_final < 40).astype(float)

# --- Portfolio ---
# Long 2-week straddle: buy call and put (each 50 contracts)
long_call_pnl = 50 * (call_2w - 9.75)      # paid 9.75 per option
long_put_pnl  = 50 * (put_2w  - 9.75)

# Short chooser (sell at 22.20)
short_chooser_pnl = -50 * (chooser_payoff - 22.20)   # = 50*(22.20 - chooser_payoff)

# Short binary put (sell at 5.00)
short_binary_pnl = -50 * (binary_payoff - 5.00)

# Total PnL per simulation (before contract size)
pnl_per_sim = long_call_pnl + long_put_pnl + short_chooser_pnl + short_binary_pnl

# Scale by contract size (3000)
pnl_scaled = pnl_per_sim * CONTRACT_SIZE

# Statistics
expected_pnl = np.mean(pnl_scaled)
std_error = np.std(pnl_scaled) / np.sqrt(n_sim)
percentiles = np.percentile(pnl_scaled, [5, 25, 50, 75, 95])

print("=== Portfolio: Long 2w Straddle + Short Chooser + Short Binary Put ===")
print(f"Upfront net cost (negative = credit): {-(50*9.75*2) + (50*22.20) + (50*5.0):.2f}")
print(f"Expected PnL (scaled by {CONTRACT_SIZE}): {expected_pnl:.2f}")
print(f"Standard error: {std_error:.2f}")
print("\nPnL percentiles (scaled):")
for p, val in zip([5, 25, 50, 75, 95], percentiles):
    print(f"  {p}%: {val:.2f}")

# Optional: show probability of loss
prob_loss = np.mean(pnl_scaled < 0)
print(f"\nProbability of loss: {prob_loss*100:.1f}%")