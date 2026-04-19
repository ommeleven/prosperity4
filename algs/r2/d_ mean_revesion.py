import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from typing import Dict, List, Tuple

class TradingBot:
    def __init__(self, maf: float = 18000.0):
        self.market_access_fee = maf          # MAF bid (only paid if accepted)
        self.position = {'OSMIUM': 0, 'PEPPER': 0}
        self.capital = 200000.0               # initial capital (adjust from round 1)
        self.hedge_ratio = 1.0
        self.spread_window = 50               # ticks for rolling OLS
        self.price_history = {'OSMIUM': [], 'PEPPER': []}
        self.zscore_entry = 1.5
        self.zscore_exit = 0.0
        self.max_position = 100               # max units per good

    def compute_spread(self, prices: pd.DataFrame) -> float:
        """Compute the spread = pepper - hedge_ratio * osmium."""
        return prices['PEPPER'] - self.hedge_ratio * prices['OSMIUM']

    def update_hedge_ratio(self, prices: pd.DataFrame) -> None:
        """Update hedge ratio using rolling OLS."""
        if len(prices) < self.spread_window:
            return
        window = prices.iloc[-self.spread_window:]
        model = OLS(window['PEPPER'], window['OSMIUM']).fit()
        self.hedge_ratio = model.params[0]

    def trade(self, state: Dict) -> List[Dict]:
        """
        Main trading function called every tick.
        state contains: timestamp, best_bid, best_ask, last_price, volume, etc.
        Returns list of orders: [{'good': 'OSMIUM', 'quantity': int, 'side': 'BUY'/'SELL'}]
        """
        # Extract current prices for both goods
        try:
            osmium_price = state['quotes']['OSMIUM']['mid']
            pepper_price = state['quotes']['PEPPER']['mid']
        except KeyError:
            return []   # missing data

        # Update price history
        self.price_history['OSMIUM'].append(osmium_price)
        self.price_history['PEPPER'].append(pepper_price)
        if len(self.price_history['OSMIUM']) > 1000:
            self.price_history['OSMIUM'].pop(0)
            self.price_history['PEPPER'].pop(0)

        # Build DataFrame for OLS
        df = pd.DataFrame({
            'OSMIUM': self.price_history['OSMIUM'],
            'PEPPER': self.price_history['PEPPER']
        })
        self.update_hedge_ratio(df)

        # Compute current spread and its z-score
        spread = self.compute_spread(df.iloc[-1])
        spreads = [self.compute_spread(df.iloc[i]) for i in range(len(df))]
        zscore = (spread - np.mean(spreads)) / (np.std(spreads) + 1e-8)

        orders = []

        # Pairs trading logic
        if zscore > self.zscore_entry and self.position['PEPPER'] > -self.max_position:
            # Spread too high → short pepper, long osmium
            orders.append({'good': 'PEPPER', 'quantity': -10, 'side': 'SELL'})
            orders.append({'good': 'OSMIUM', 'quantity': 10, 'side': 'BUY'})
            self.position['PEPPER'] -= 10
            self.position['OSMIUM'] += 10
        elif zscore < -self.zscore_entry and self.position['PEPPER'] < self.max_position:
            # Spread too low → long pepper, short osmium
            orders.append({'good': 'PEPPER', 'quantity': 10, 'side': 'BUY'})
            orders.append({'good': 'OSMIUM', 'quantity': -10, 'side': 'SELL'})
            self.position['PEPPER'] += 10
            self.position['OSMIUM'] -= 10
        elif abs(zscore) < self.zscore_exit:
            # Exit positions
            if self.position['PEPPER'] > 0:
                orders.append({'good': 'PEPPER', 'quantity': -self.position['PEPPER'], 'side': 'SELL'})
                orders.append({'good': 'OSMIUM', 'quantity': self.position['PEPPER'], 'side': 'BUY'})
            elif self.position['PEPPER'] < 0:
                orders.append({'good': 'PEPPER', 'quantity': -self.position['PEPPER'], 'side': 'BUY'})
                orders.append({'good': 'OSMIUM', 'quantity': self.position['PEPPER'], 'side': 'SELL'})
            self.position['PEPPER'] = 0
            self.position['OSMIUM'] = 0

        # Apply risk management: stop-loss if unrealized PnL < -5000
        # (Simplified – in production we'd compute PnL from portfolio)
        return orders

# The platform will instantiate the bot and call trade() on each tick.
# To include MAF, we simply set it when creating the bot.
bot = TradingBot(maf=18000.0)