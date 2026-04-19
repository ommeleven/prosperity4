import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from typing import Dict, List

class PairsTradingBot:
    def __init__(self, maf: float = 18000.0):
        self.market_access_fee = maf
        self.position = {'OSMIUM': 0, 'PEPPER': 0}
        self.capital = 200000.0          # starting capital (adjust from round 1)
        self.hedge_ratio = 1.0
        self.window = 50                 # rolling OLS window
        self.price_hist = {'OSMIUM': [], 'PEPPER': []}
        self.entry_z = 1.5
        self.exit_z = 0.0
        self.max_pos = 100               # max units per good

    def _spread(self, osmium: float, pepper: float) -> float:
        return pepper - self.hedge_ratio * osmium

    def _update_hedge_ratio(self, df: pd.DataFrame) -> None:
        if len(df) < self.window:
            return
        window = df.iloc[-self.window:]
        model = OLS(window['PEPPER'], window['OSMIUM']).fit()
        self.hedge_ratio = model.params[0]

    def trade(self, state: Dict) -> List[Dict]:
        # Extract mid prices
        try:
            osmium = state['quotes']['OSMIUM']['mid']
            pepper = state['quotes']['PEPPER']['mid']
        except:
            return []

        # Update history
        self.price_hist['OSMIUM'].append(osmium)
        self.price_hist['PEPPER'].append(pepper)
        if len(self.price_hist['OSMIUM']) > 1000:
            self.price_hist['OSMIUM'].pop(0)
            self.price_hist['PEPPER'].pop(0)

        df = pd.DataFrame(self.price_hist)
        self._update_hedge_ratio(df)

        # Compute z-score of spread
        spreads = [self._spread(df['OSMIUM'].iloc[i], df['PEPPER'].iloc[i]) for i in range(len(df))]
        current_spread = spreads[-1]
        z = (current_spread - np.mean(spreads)) / (np.std(spreads) + 1e-8)

        orders = []
        # Long spread = buy pepper, short osmium
        if z > self.entry_z and self.position['PEPPER'] > -self.max_pos:
            orders.append({'good': 'PEPPER', 'quantity': -10, 'side': 'SELL'})   # short pepper
            orders.append({'good': 'OSMIUM', 'quantity': 10, 'side': 'BUY'})      # long osmium
            self.position['PEPPER'] -= 10
            self.position['OSMIUM'] += 10
        elif z < -self.entry_z and self.position['PEPPER'] < self.max_pos:
            orders.append({'good': 'PEPPER', 'quantity': 10, 'side': 'BUY'})
            orders.append({'good': 'OSMIUM', 'quantity': -10, 'side': 'SELL'})
            self.position['PEPPER'] += 10
            self.position['OSMIUM'] -= 10
        elif abs(z) < self.exit_z:
            # Flatten positions
            if self.position['PEPPER'] != 0:
                orders.append({'good': 'PEPPER', 'quantity': -self.position['PEPPER'],
                               'side': 'SELL' if self.position['PEPPER'] > 0 else 'BUY'})
                orders.append({'good': 'OSMIUM', 'quantity': self.position['PEPPER'],
                               'side': 'BUY' if self.position['PEPPER'] > 0 else 'SELL'})
                self.position = {'OSMIUM': 0, 'PEPPER': 0}
        return orders

bot = PairsTradingBot(maf=18000.0)