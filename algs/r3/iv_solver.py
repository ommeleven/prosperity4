from scipy.optimize import brentq
import numpy as np
from scipy.stats import norm

def get_strike(product):
    if "VEV_" in product:
        return float(product.split("_")[1])
    return None

def bs_call_price(S, K, T, sigma):
    d1 = (np.log(S/K) + 0.5*sigma**2*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)

    return S*norm.cdf(d1) - K*norm.cdf(d2)

def implied_vol(S, K, T, price):
    def f(sigma):
        return bs_call_price(S, K, T, sigma) - price

    try:
        return brentq(f, 1e-4, 5)
    except:
        return np.nan
    
def compute_iv(df):
    results = []

    S = df[df["product"] == "VELVETFRUIT_EXTRACT"][["timestamp", "mid"]]
    S = S.rename(columns={"mid": "S"})

    df = df.merge(S, on="timestamp")

    for _, row in df.iterrows():
        K = get_strike(row["product"])
        if K is None:
            continue

        T = 1.0  # simplify first pass
        price = row["mid"]
        S_val = row["S"]

        iv = implied_vol(S_val, K, T, price)

        results.append([row["timestamp"], K, iv])

    return pd.DataFrame(results, columns=["timestamp", "strike", "iv"])