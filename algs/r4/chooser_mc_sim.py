import numpy as np

# Parameters (same as problem)
S0 = 50.0
r = 0.0
vol = 2.51
T_total = 3/52          # 3 weeks in years (approx 0.05769)
T_choice = 2/52         # 2 weeks (0.03846)
dt = 1/(252*4)          # time per step (approx 0.000992)
steps_total = int(T_total / dt)   # 60 steps
steps_choice = int(T_choice / dt) # 40 steps

n_sim = 100_000
np.random.seed(42)

# Simulate full paths (60 steps)
S = np.zeros((n_sim, steps_total+1))
S[:,0] = S0
for i in range(steps_total):
    Z = np.random.randn(n_sim)
    S[:, i+1] = S[:, i] * np.exp((r - 0.5*vol**2)*dt + vol*np.sqrt(dt)*Z)

# Extract prices at choice time (step 40) and expiry (step 60)
S_choice = S[:, steps_choice]   # 14 days
S_expiry = S[:, -1]             # 21 days

# Chooser payoff
payoff = np.where(S_choice > 50,
                  np.maximum(S_expiry - 50, 0),
                  np.maximum(50 - S_expiry, 0))

fair_value = np.mean(payoff)
std_error = np.std(payoff) / np.sqrt(n_sim)

print(f"Fair value of chooser option: {fair_value:.4f} ± {std_error:.4f}")