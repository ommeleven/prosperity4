import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from scipy.optimize import brentq

# 1. Black-Scholes Call Formula
def bs_call_price(S, K, T, r, sigma):
    if sigma <= 0: return max(0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

# 2. Implied Volatility Solver
def calculate_iv(market_price, S, K, T, r=0.0):
    intrinsic = max(0, S - K)
    # If market price is below intrinsic or too low, IV is undefined
    if market_price <= intrinsic + 1e-5: return np.nan
    
    # Solve for sigma where BS_Price(sigma) - Market_Price = 0
    try:
        return brentq(lambda sig: bs_call_price(S, K, T, r, sig) - market_price, 1e-6, 5.0)
    except:
        return np.nan

# 3. Load Data (Using Day 2 for analysis)
df = pd.read_csv('/Users/HP/src/prosperity4/algs/r3/prices_round_3_day_2.csv', sep=';')
T_years = 6 / 365.0 # TTE = 6 days
S_market = df[df['product'] == 'VELVETFRUIT_EXTRACT']['mid_price'].mean()

# Aggregate Voucher Prices
vouchers = df[df['product'].str.contains('VEV_')].groupby('product')['mid_price'].mean().reset_index()
vouchers['strike'] = vouchers['product'].apply(lambda x: int(x.split('_')[1]))
vouchers = vouchers.sort_values('strike')

# 4. Compute IV for each Strike
vouchers['iv'] = vouchers.apply(
    lambda row: calculate_iv(row['mid_price'], S_market, row['strike'], T_years), axis=1
)

# 5. Plotting the Smile
vouchers_clean = vouchers.dropna(subset=['iv'])
plt.figure(figsize=(10, 6))
plt.plot(vouchers_clean['strike'], vouchers_clean['iv'], 'po-', label='Market IV')

# Fit a 2nd degree polynomial (the 'smile' curve)
z = np.polyfit(vouchers_clean['strike'], vouchers_clean['iv'], 2)
p = np.poly1d(z)
strike_range = np.linspace(vouchers_clean['strike'].min(), vouchers_clean['strike'].max(), 100)
plt.plot(strike_range, p(strike_range), "r--", alpha=0.6, label='Smile Fit')

plt.title('Volatility Smile: Velvetfruit Extract Vouchers')
plt.xlabel('Strike Price')
plt.ylabel('Annualized Implied Volatility')
plt.axvline(S_market, color='green', linestyle=':', label=f'Spot Price ({S_market:.1f})')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()