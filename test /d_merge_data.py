import pandas as pd
import numpy as np
from statsmodels.regression.linear_model import OLS
import glob

# ---- Load all price files ----
 
from pathlib import Path

folder_path = Path("/Users/HP/src/prosperity4/ROUND_2")
price_files = sorted(folder_path.glob("prices_round_2_day_*.csv"))
dfs = []
for f in price_files:
    df = pd.read_csv(f)
    # Extract day from filename (e.g., day_-1)
    day = f.split('_')[-1].replace('.csv', '')
    df['day'] = day
    dfs.append(df)

prices = pd.concat(dfs, ignore_index=True)
# Pivot so each row has both products
prices = prices.pivot(index=['timestamp','day'], columns='product', 
                      values=['bid_price_1','ask_price_1','mid_price','bid_volume_1','ask_volume_1'])
prices.columns = [f'{col[1]}_{col[0]}' for col in prices.columns]  # e.g., 'ASH_COATED_OSMIUM_mid_price'
prices.reset_index(inplace=True)
prices['timestamp'] = pd.to_datetime(prices['timestamp'])

# ---- Load trade files (optional) ----
trade_files = sorted(glob.glob("trades_round_2_day_*.csv"))
trades = pd.concat([pd.read_csv(f) for f in trade_files], ignore_index=True)
trades['timestamp'] = pd.to_datetime(trades['timestamp'])