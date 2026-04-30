import numpy as np

# --- Configuration ---
S0 = 50.0
VOL = 2.51  # 251% annualized
R = 0.0     # Zero risk-neutral drift
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
CONTRACT_SIZE = 3000
NUM_SIMULATIONS = 100000

# Function to convert weeks to trading steps
def get_steps(weeks):
    return int(round(weeks * 5 * STEPS_PER_DAY))

def run_simulation():
    # Simulation Parameters
    dt = 1 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
    total_steps = get_steps(3)  # Max duration is 3 weeks
    
    # Generate GBM Paths: S_t = S_{t-1} * exp((r - 0.5*sigma^2)dt + sigma*sqrt(dt)*Z)
    nudt = (R - 0.5 * VOL**2) * dt
    vsqdt = VOL * np.sqrt(dt)
    z = np.random.normal(0, 1, (NUM_SIMULATIONS, total_steps))
    path_returns = np.exp(nudt + vsqdt * z)
    paths = np.cumprod(path_returns, axis=1)
    # Prepend S0 to the paths
    paths = np.hstack([np.ones((NUM_SIMULATIONS, 1)) * S0, paths * S0])

    # Timesteps for expiries
    t_14 = get_steps(2)
    t_21 = get_steps(3)

    # --- Payoff Definitions ---
    # Long Positions
    payoff_50_C_3w = np.maximum(paths[:, t_21] - 50, 0)      # AC_50_C (Buy)
    payoff_50_P_2w = np.maximum(50 - paths[:, t_14], 0)      # AC_50_P_2 (Buy)
    payoff_50_C_2w = np.maximum(paths[:, t_14] - 50, 0)      # AC_50_C_2 (Buy)
    
    # AC_45_KO: Put K=45, Knockout if S < 35 (Buy)
    knocked_out = np.any(paths[:, :t_21+1] < 35, axis=1)
    payoff_45_KO = np.where(knocked_out, 0, np.maximum(45 - paths[:, t_21], 0))

    # Short Positions
    payoff_50_P_3w = np.maximum(50 - paths[:, t_21], 0)      # AC_50_P (Sell)
    
    # AC_50_CO: Chooser at 2 weeks, Expiry 3 weeks (Sell)
    # Buyer chooses side at t_14 based on which is ITM
    chooser_payoff = []
    for i in range(NUM_SIMULATIONS):
        if paths[i, t_14] > 50: # Becomes a Call
            chooser_payoff.append(max(paths[i, t_21] - 50, 0))
        else: # Becomes a Put
            chooser_payoff.append(max(50 - paths[i, t_21], 0))
    payoff_chooser = np.array(chooser_payoff)

    # AC_40_BP: Binary Put, K=40, Payoff=10 (Sell)
    payoff_binary_put = np.where(paths[:, t_21] < 40, 10, 0)

    # --- Cost Basis (Using Mid Prices for fair PnL assessment) ---
    # Adjust these to your actual entry prices if needed
    costs = {
        "AC_50_C_3w": 12.025,
        "AC_50_P_2w": 9.725,
        "AC_50_C_2w": 9.725,
        "AC_45_KO": 0.1625,
        "AC_50_P_3w": 12.025,
        "AC_50_CO": 22.25,
        "AC_40_BP": 5.05
    }

    # Calculate Individual PnL
    pnl_long = (payoff_50_C_3w - costs["AC_50_C_3w"]) + \
               (payoff_50_P_2w - costs["AC_50_P_2w"]) + \
               (payoff_50_C_2w - costs["AC_50_C_2w"]) + \
               (payoff_45_KO - costs["AC_45_KO"])
    
    pnl_short = (costs["AC_50_P_3w"] - payoff_50_P_3w) + \
                (costs["AC_50_CO"] - payoff_chooser) + \
                (costs["AC_40_BP"] - payoff_binary_put)

    total_pnl = (pnl_long + pnl_short) * CONTRACT_SIZE

    # Results
    print(f"--- Portfolio Performance (after {NUM_SIMULATIONS} simulations) ---")
    print(f"Expected PnL: {np.mean(total_pnl):,.2f} XIRECs")
    print(f"Std Deviation: {np.std(total_pnl):,.2f}")
    print(f"Max Loss:      {np.min(total_pnl):,.2f}")
    print(f"Max Gain:      {np.max(total_pnl):,.2f}")
    print(f"Prob. of Profit: {np.mean(total_pnl > 0) * 100:.2f}%")

if __name__ == "__main__":
    run_simulation()