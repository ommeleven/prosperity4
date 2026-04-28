import numpy as np

SELL = 920
LOW = 670
STEP = 5
N = 51  # number of discrete values

bids = np.arange(LOW, SELL + 1, STEP)

# ----- Your Desmos functions -----

def f1(b1):
    return ((b1 - LOW) / STEP) * (SELL - b1) / N


def M(b2, b_avg):
    if b2 > b_avg:
        return SELL - b2
    else:
        return ((SELL - b_avg) ** 3) / ((SELL - b2) ** 2)


def f_total(b1, b2, b_avg):
    if b2 <= b1:
        return -1e9  # invalid

    second_mass = (b2 - b1) / STEP
    return f1(b1) + second_mass * M(b2, b_avg) / N


# ----- Grid search -----

def optimize_given_avg(b_avg):
    best = None
    best_val = -1e9

    for b1 in bids:
        for b2 in bids:
            val = f_total(b1, b2, b_avg)
            if val > best_val:
                best_val = val
                best = (b1, b2)

    return best, best_val


# ----- Fixed-point (equilibrium finder) -----

def find_equilibrium(init_avg=880, iters=20, alpha=0.5):
    b_avg = init_avg

    for _ in range(iters):
        (b1, b2), val = optimize_given_avg(b_avg)

        # update belief about avg_b2
        b_avg = alpha * b_avg + (1 - alpha) * b2

    return {
        "b1": b1,
        "b2": b2,
        "avg_b2": b_avg,
        "pnl": val
    }


# ----- Run -----

if __name__ == "__main__":
    # Best response to fixed assumptions
    for avg in [850, 870, 890, 900]:
        best, val = optimize_given_avg(avg)
        print(f"avg_b2={avg} -> best={best}, pnl={val:.4f}")

    print("\nEquilibrium approximation:")
    print(find_equilibrium())