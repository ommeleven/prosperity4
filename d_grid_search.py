from datamodel import Order, OrderDepth, TradingState, Product
from typing import Dict, List
import statistics

class Trader:
    def __init__(self):
        # Optimized parameters from backtesting [citation:5]
        self.optimal_edges = {
            'ASH_COATED_OSMIUM': 3,    # More volatile = wider spread
            'INTARIAN_PEPPER_ROOT': 1   # Stable = tight spread
        }
        
        self.position_limits = {'ASH_COATED_OSMIUM': 80, 'INTARIAN_PEPPER_ROOT': 80}
        self.fair_value_cache = {'ASH_COATED_OSMIUM': [], 'INTARIAN_PEPPER_ROOT': []}
        
        # Track market maker quotes to find true fair value [citation:5]
        self.mm_quotes = {'ASH_COATED_OSMIUM': [], 'INTARIAN_PEPPER_ROOT': []}
        
    def extract_market_maker_mid(self, product: str, order_depth: OrderDepth) -> float:
        """
        Extract the large market maker's mid price.
        The market maker typically places large quantities at consistent prices [citation:5]
        """
        # Find the price levels with largest volume
        buy_volumes = sorted([(v, p) for p, v in order_depth.buy_orders.items()], reverse=True)
        sell_volumes = sorted([(v, p) for p, v in order_depth.sell_orders.items()], reverse=True)
        
        if buy_volumes and sell_volumes:
            # Market maker likely has largest volume at consistent price
            mm_bid = buy_volumes[0][1] if buy_volumes else None
            mm_ask = sell_volumes[0][1] if sell_volumes else None
            
            if mm_bid and mm_ask:
                mm_mid = (mm_bid + mm_ask) / 2
                self.mm_quotes[product].append(mm_mid)
                if len(self.mm_quotes[product]) > 10:
                    self.mm_quotes[product].pop(0)
                return statistics.mean(self.mm_quotes[product]) if self.mm_quotes[product] else mm_mid
        
        # Fallback to standard mid
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        return (best_bid + best_ask) / 2
    
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        result = {}
        
        for product in ['ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT']:
            if product not in state.order_depths:
                continue
                
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            limit = self.position_limits[product]
            
            # Get true fair value from market maker
            fair_value = self.extract_market_maker_mid(product, order_depth)
            
            orders = []
            edge = self.optimal_edges[product]
            
            # Inventory-based adjustment (grid search optimized) [citation:3][citation:5]
            position_ratio = position / limit if limit > 0 else 0
            inventory_penalty = position_ratio * edge * 0.5
            
            # Market making at optimal edge
            bid_price = int(fair_value - edge - inventory_penalty)
            ask_price = int(fair_value + edge - inventory_penalty)
            
            # Size based on inventory (more when balanced)
            base_size = 10
            if abs(position_ratio) < 0.3:
                size = base_size
            elif abs(position_ratio) < 0.6:
                size = base_size // 2
            else:
                size = base_size // 4
            
            # Place orders
            if position < limit * 0.9:
                orders.append(Order(product, bid_price, size))
            if position > -limit * 0.9:
                orders.append(Order(product, ask_price, -size))
            
            # Take obvious mispricings
            for price, volume in order_depth.buy_orders.items():
                if price > fair_value + edge * 2:  # Significant premium
                    take_vol = min(volume, limit + position, 20)
                    if take_vol > 0:
                        orders.append(Order(product, price, -take_vol))
                        break
            
            for price, volume in order_depth.sell_orders.items():
                if price < fair_value - edge * 2:  # Significant discount
                    take_vol = min(volume, limit - position, 20)
                    if take_vol > 0:
                        orders.append(Order(product, price, take_vol))
                        break
            
            result[product] = orders
            
        return result