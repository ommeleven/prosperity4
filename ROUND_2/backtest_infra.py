import pandas as pd
import numpy as np
import glob
from typing import List, Dict

# =============================================================================
# CONFIGURATION
# =============================================================================
MARKET_ACCESS_FEE_BID = 10000
BASE_MAX_POSITION = 1000
TRADING_CAPITAL = 1_000_000
TRANSACTION_COST = 0.001

INVEST_RESEARCH = 30
INVEST_SCALE = 40
INVEST_SPEED = 30
BUDGET_TOTAL = 50_000

# =============================================================================
# 1. LOAD AND MERGE DATA (FIXED)
# =============================================================================
def load_price_files() -> pd.DataFrame:
    price_files = sorted(glob.glob("prices_round_2_day_*.csv"))
    if not price_files:
        raise FileNotFoundError("No price files found.")
    
    dfs = []
    for f in price_files:
        with open(f, 'r') as file:
            sep = ';' if ';' in file.readline() else ','
        df = pd.read_csv(f, sep=sep)
        df.columns = df.columns.str.lower().str.strip()
        
        if 'mid_price' in df.columns:
            df = df[['timestamp', 'product', 'mid_price']]
        elif 'bid_price_1' in df.columns and 'ask_price_1' in df.columns:
            df['mid_price'] = (df['bid_price_1'] + df['ask_price_1']) / 2
            df = df[['timestamp', 'product', 'mid_price']]
        else:
            raise ValueError(f"Missing price columns in {f}")
        dfs.append(df)
    
    df_all = pd.concat(dfs, ignore_index=True)
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])
    df_all['product'] = df_all['product'].str.lower().str.replace(' ', '_')
    
    # Remove duplicates by taking the last mid_price per (timestamp, product)
    df_all = df_all.sort_values('timestamp')
    df_all = df_all.groupby(['timestamp', 'product'], as_index=False).last()
    return df_all

price_df = load_price_files()
price_pivot = price_df.pivot_table(index='timestamp', columns='product', values='mid_price', aggfunc='last')
price_pivot = price_pivot.ffill().dropna().reset_index()

product_cols = [c for c in price_pivot.columns if c != 'timestamp']
print(f"Loaded {len(price_pivot)} price points. Products: {product_cols}")

# =============================================================================
# 2. MARKET ACCESS FEE
# =============================================================================
def max_position_size(bid, base_max):
    return base_max * (1 + bid / 10000)

MAX_POSITION = max_position_size(MARKET_ACCESS_FEE_BID, BASE_MAX_POSITION)
print(f"Max position per asset: {MAX_POSITION:.0f} units")

# =============================================================================
# 3. SIMULATOR (unchanged)
# =============================================================================
class Trade:
    def __init__(self, timestamp, asset, side, quantity, price, fee=0):
        self.timestamp = timestamp
        self.asset = asset
        self.side = side
        self.quantity = quantity
        self.price = price
        self.fee = fee

class TradingSimulator:
    def __init__(self, price_df, initial_capital, max_pos, txn_cost):
        self.df = price_df.copy()
        self.cash = initial_capital
        self.position = {col: 0 for col in product_cols}
        self.max_position = max_pos
        self.txn_cost = txn_cost
        self.trades = []
        self.ts_to_idx = {ts: i for i, ts in enumerate(self.df['timestamp'])}
    
    def get_price(self, timestamp, asset):
        idx = self.ts_to_idx.get(timestamp)
        if idx is None:
            raise ValueError(f"Timestamp {timestamp} not found.")
        return self.df.iloc[idx][asset]
    
    def execute_trade(self, timestamp, asset, side, quantity):
        if quantity <= 0:
            return
        price = self.get_price(timestamp, asset)
        current_pos = self.position[asset]
        
        if side == 'buy':
            new_pos = current_pos + quantity
            if new_pos > self.max_position:
                quantity = self.max_position - current_pos
                if quantity <= 0:
                    return
        else:
            new_pos = current_pos - quantity
            if new_pos < -self.max_position:
                quantity = current_pos + self.max_position
                if quantity <= 0:
                    return
        
        cost = quantity * price
        fee = cost * self.txn_cost
        total_cost = cost + fee
        
        if side == 'buy':
            if self.cash < total_cost:
                affordable_qty = int(self.cash / (price * (1 + self.txn_cost)))
                if affordable_qty <= 0:
                    return
                quantity = affordable_qty
                cost = quantity * price
                fee = cost * self.txn_cost
                total_cost = cost + fee
            self.cash -= total_cost
            self.position[asset] += quantity
        else:
            self.cash += cost - fee
            self.position[asset] -= quantity
        
        self.trades.append(Trade(timestamp, asset, side, quantity, price, fee))
    
    def run_manual_trades(self, manual_trades):
        for spec in manual_trades:
            ts = pd.to_datetime(spec['timestamp'])
            if ts not in self.ts_to_idx:
                print(f"Warning: {ts} not in data, skipping.")
                continue
            asset = spec['asset']
            if asset not in self.position:
                print(f"Warning: unknown asset '{asset}'")
                continue
            self.execute_trade(ts, asset, spec['side'], spec['quantity'])
    
    def final_pnl(self):
        final_row = self.df.iloc[-1]
        portfolio_value = self.cash
        for asset in self.position:
            portfolio_value += self.position[asset] * final_row[asset]
        return portfolio_value - TRADING_CAPITAL

# =============================================================================
# 4. INVESTMENT ALLOCATION
# =============================================================================
def research_value(pct):
    if pct <= 0: return 0.0
    return 200_000 * np.log(1 + pct) / np.log(101)

def scale_value(pct):
    return 7.0 * (pct / 100)

def estimate_speed_multiplier(your_pct, typical_others=None):
    if typical_others is None:
        typical_others = [50, 60, 40, 30, 70, 20, 10, 80, 90, 25]
    all_pcts = [your_pct] + typical_others
    unique = sorted(set(all_pcts), reverse=True)
    rank_map = {v: i+1 for i, v in enumerate(unique)}
    ranks = [rank_map[v] for v in all_pcts]
    your_rank = rank_map[your_pct]
    min_r, max_r = min(ranks), max(ranks)
    if max_r == min_r:
        return 0.5
    return 0.9 - (0.8 * (your_rank - min_r) / (max_r - min_r))

research = research_value(INVEST_RESEARCH)
scale = scale_value(INVEST_SCALE)
speed = estimate_speed_multiplier(INVEST_SPEED)
gross_mult = research * scale * speed
budget_used = BUDGET_TOTAL * (INVEST_RESEARCH + INVEST_SCALE + INVEST_SPEED) / 100

print(f"\nInvestment multiplier: {gross_mult:,.0f} (budget used: {budget_used:,.0f})")

# =============================================================================
# 5. MAIN
# =============================================================================
def main():
    sim = TradingSimulator(price_pivot, TRADING_CAPITAL, MAX_POSITION, TRANSACTION_COST)
    
    # ---- EDIT YOUR MANUAL TRADES HERE ----
    manual_trades = [
        # Example (replace with actual timestamps and asset names from product_cols)
        # {'timestamp': '2026-04-17 09:30:00', 'asset': 'ash_coated_osmium', 'side': 'buy', 'quantity': 500},
    ]
    
    sim.run_manual_trades(manual_trades)
    trading_pnl = sim.final_pnl()
    
    print(f"\nTRADING PnL: {trading_pnl:,.2f} XIRECs")
    print(f"Trades executed: {len(sim.trades)}")
    
    combined_pnl = (trading_pnl * gross_mult) - budget_used
    print(f"COMBINED PnL (after investment): {combined_pnl:,.2f} XIRECs")
    
    if trading_pnl >= 200_000:
        print("✓ Target achieved!")
    else:
        print(f"✗ Short by {200_000 - trading_pnl:,.2f} XIRECs")
    
    if sim.trades:
        pd.DataFrame([vars(t) for t in sim.trades]).to_csv("manual_trades_log.csv", index=False)
        print("Trade log saved.")

if __name__ == "__main__":
    main()