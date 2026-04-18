from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import numpy as np
from collections import deque

class Trader:
    def __init__(self):
        self.price_history = {
            'ASH_COATED_OSMIUM': deque(maxlen=20),
            'INTARIAN_PEPPER_ROOT': deque(maxlen=10)
        }
        self.position_limits = {'ASH_COATED_OSMIUM': 80, 'INTARIAN_PEPPER_ROOT': 80}
        self.zscore_threshold = 1.5  # Mean reversion trigger
        
    def calculate_zscore(self, product: str, current_price: float) -> float:
        """Calculate how many std devs price is from mean"""
        if len(self.price_history[product]) < 5:
            return 0
            
        prices = list(self.price_history[product])
        mean = np.mean(prices)
        std = np.std(prices)
        
        if std == 0:
            return 0
        return (current_price - mean) / std
    
    def get_best_prices(self, order_depth: OrderDepth) -> tuple:
        """Get best bid and ask"""
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask
    
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        result = {}
        
        for product in ['ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT']:
            if product not in state.order_depths:
                continue
                
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            limit = self.position_limits[product]
            
            best_bid, best_ask = self.get_best_prices(order_depth)
            if best_bid is None or best_ask is None:
                continue
                
            mid_price = (best_bid + best_ask) / 2
            self.price_history[product].append(mid_price)
            
            # Calculate deviation from mean
            zscore = self.calculate_zscore(product, mid_price)
            
            orders = []
            
            # Mean reversion trading
            if zscore > self.zscore_threshold:  # Price too high - expect drop
                # Sell aggressively
                sell_price = best_bid
                quantity = min(limit + position, 15)  # Sell up to position limit
                if quantity > 0:
                    orders.append(Order(product, sell_price, -quantity))
                    
            elif zscore < -self.zscore_threshold:  # Price too low - expect rise
                # Buy aggressively
                buy_price = best_ask
                quantity = min(limit - position, 15)  # Buy up to position limit
                if quantity > 0:
                    orders.append(Order(product, buy_price, quantity))
            
            # If near neutral, market make
            elif abs(zscore) < 0.5:
                if position > -limit * 0.8:
                    orders.append(Order(product, best_bid, 5))
                if position < limit * 0.8:
                    orders.append(Order(product, best_ask, -5))
            
            result[product] = orders
            
        return result