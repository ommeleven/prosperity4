from datamodel import Order, OrderDepth, TradingState, Product
from typing import Dict, List, Tuple
import statistics

class Trader:
    def __init__(self):
        # Position limits for each product
        self.position_limits = {
            'ASH_COATED_OSMIUM': 80,
            'INTARIAN_PEPPER_ROOT': 80
        }
        
        # Track fair value estimates
        self.fair_values = {
            'ASH_COATED_OSMIUM': [],  # Store historical fair values
            'INTARIAN_PEPPER_ROOT': []
        }
        
        # Parameters for each product
        self.params = {
            'ASH_COATED_OSMIUM': {
                'window': 10,      # Rolling window for volatility
                'edge': 2,         # Market making edge
                'position_scalar': 0.5  # Aggressiveness based on inventory
            },
            'INTARIAN_PEPPER_ROOT': {
                'window': 5,
                'edge': 1,
                'position_scalar': 0.3
            }
        }
    
    def calculate_fair_value(self, product: str, order_depth: OrderDepth) -> float:
        """Calculate fair value using market maker mid-price"""
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if best_bid is None or best_ask is None:
            # Use last known fair value
            return self.fair_values[product][-1] if self.fair_values[product] else 10000
        
        # Mid-price as fair value estimate
        mid_price = (best_bid + best_ask) / 2
        
        # Track historical for smoothing
        self.fair_values[product].append(mid_price)
        if len(self.fair_values[product]) > self.params[product]['window']:
            self.fair_values[product].pop(0)
        
        # Return smoothed value
        if len(self.fair_values[product]) > 0:
            return statistics.mean(self.fair_values[product])
        return mid_price
    
    def get_position_adjustment(self, product: str, position: int) -> float:
        """Adjust pricing based on current inventory"""
        limit = self.position_limits[product]
        ratio = abs(position) / limit if limit > 0 else 0
        scalar = self.params[product]['position_scalar']
        
        # More aggressive when close to limits
        if position > 0:
            return -ratio * scalar * self.params[product]['edge']  # Lower bids, raise asks
        elif position < 0:
            return ratio * scalar * self.params[product]['edge']   # Raise bids, lower asks
        return 0
    
    def market_make(self, product: str, fair_value: float, position: int) -> List[Order]:
        """Generate market making orders"""
        orders = []
        adj = self.get_position_adjustment(product, position)
        edge = self.params[product]['edge']
        
        # Bid (buy) price - slightly below fair value
        bid_price = int(fair_value - edge + adj)
        # Ask (sell) price - slightly above fair value
        ask_price = int(fair_value + edge + adj)
        
        # Conservative quantities based on position
        limit = self.position_limits[product]
        max_quantity = min(10, limit - abs(position))
        
        if max_quantity > 0:
            # Place both bid and ask
            orders.append(Order(product, bid_price, max_quantity))
            orders.append(Order(product, ask_price, -max_quantity))
        
        return orders
    
    def market_take(self, product: str, order_depth: OrderDepth, fair_value: float, position: int) -> List[Order]:
        """Take profitable opportunities"""
        orders = []
        limit = self.position_limits[product]
        
        # Check for profitable bids (someone buying above fair value)
        for price, volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if price > fair_value + self.params[product]['edge']:
                # Sell to them
                trade_vol = min(volume, limit + position)  # Can't go short beyond limit
                if trade_vol > 0:
                    orders.append(Order(product, price, -trade_vol))
                    break  # Take best opportunity only
        
        # Check for profitable asks (someone selling below fair value)
        for price, volume in sorted(order_depth.sell_orders.items()):
            if price < fair_value - self.params[product]['edge']:
                # Buy from them
                trade_vol = min(volume, limit - position)  # Can't go long beyond limit
                if trade_vol > 0:
                    orders.append(Order(product, price, trade_vol))
                    break
        
        return orders
    
    def clear_position(self, product: str, order_depth: OrderDepth, fair_value: float, position: int) -> List[Order]:
        """Reduce position when near limits"""
        orders = []
        limit = self.position_limits[product]
        
        # Too long - need to sell
        if position > limit * 0.7:
            # Sell at bid prices
            for price, volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if price >= fair_value:  # Don't sell at loss
                    trade_vol = min(volume, position)
                    orders.append(Order(product, price, -trade_vol))
                    break
        
        # Too short - need to buy
        elif position < -limit * 0.7:
            # Buy at ask prices
            for price, volume in sorted(order_depth.sell_orders.items()):
                if price <= fair_value:  # Don't buy at loss
                    trade_vol = min(volume, -position)
                    orders.append(Order(product, price, trade_vol))
                    break
        
        return orders
    
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """Main trading loop"""
        result = {}
        
        for product in ['ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT']:
            if product not in state.order_depths:
                continue
            
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            
            # Calculate fair value
            fair_value = self.calculate_fair_value(product, order_depth)
            
            # Generate orders
            orders = []
            orders.extend(self.market_take(product, order_depth, fair_value, position))
            orders.extend(self.market_make(product, fair_value, position))
            orders.extend(self.clear_position(product, order_depth, fair_value, position))
            
            result[product] = orders
        
        # Required return format
        conversions = 0
        trader_data = ""
        
        return result, conversions, trader_data