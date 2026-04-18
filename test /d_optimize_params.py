# optimize_parameters.py
import itertools
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import copy

class ParameterOptimizer:
    def __init__(self, historical_data):
        """
        historical_data: List of TradingState snapshots from your logs
        """
        self.historical_data = historical_data
        self.results = []
        
    def backtest_strategy(self, params, trader_instance):
        """Run backtest with given parameters"""
        total_profit = 0
        position = {'ASH_COATED_OSMIUM': 0, 'INTARIAN_PEPPER_ROOT': 0}
        
        for timestep in self.historical_data:
            # Set parameters in trader
            for key, value in params.items():
                setattr(trader_instance, key, value)
            
            # Run trading logic
            orders, _, _ = trader_instance.run(timestep)
            
            # Simulate execution (simplified)
            profit_delta = self.simulate_execution(orders, timestep.order_depths, position)
            total_profit += profit_delta
        
        return total_profit
    
    def simulate_execution(self, orders, order_depths, position):
        """Simulate order execution based on market depth"""
        profit = 0
        
        for product, order_list in orders.items():
            depth = order_depths.get(product)
            if not depth:
                continue
                
            for order in order_list:
                if order.quantity > 0:  # Buy order
                    # Check if ask price exists and is <= order price
                    best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
                    if best_ask and best_ask <= order.price:
                        # Execute at best ask
                        exec_price = best_ask
                        exec_quantity = min(order.quantity, depth.sell_orders[best_ask])
                        profit -= exec_price * exec_quantity
                        position[product] += exec_quantity
                        
                else:  # Sell order
                    # Check if bid price exists and is >= order price
                    best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
                    if best_bid and best_bid >= order.price:
                        # Execute at best bid
                        exec_price = best_bid
                        exec_quantity = min(-order.quantity, depth.buy_orders[best_bid])
                        profit += exec_price * exec_quantity
                        position[product] -= exec_quantity
        
        return profit
    
    def grid_search(self, param_ranges):
        """
        param_ranges: Dict of parameter names to lists of values to test
        Example: {'edge': [1, 2, 3, 4], 'position_scalar': [0.3, 0.5, 0.7]}
        """
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        print("Starting grid search...")
        print(f"Testing {np.prod([len(v) for v in param_values])} combinations")
        
        for combination in itertools.product(*param_values):
            params = dict(zip(param_names, combination))
            
            # Create fresh trader instance each time
            from your_trader import Trader  # Import your actual trader class
            trader = Trader()
            
            profit = self.backtest_strategy(params, trader)
            
            self.results.append({
                'params': params,
                'profit': profit
            })
            
            print(f"Params: {params} -> Profit: {profit:,.2f}")
        
        # Find best parameters
        best_result = max(self.results, key=lambda x: x['profit'])
        
        print("\n" + "="*60)
        print("OPTIMIZATION RESULTS")
        print("="*60)
        print(f"Best Parameters: {best_result['params']}")
        print(f"Best Profit: {best_result['profit']:,.2f}")
        
        return best_result

# Usage example
if __name__ == "__main__":
    # Load your historical data
    with open('historical_market_data.json', 'r') as f:
        historical_data = json.load(f)
    
    optimizer = ParameterOptimizer(historical_data)
    
    # Define parameter ranges to test
    param_ranges = {
        'edge': [1, 2, 3, 4, 5],
        'position_scalar': [0.2, 0.4, 0.6, 0.8],
        'window': [5, 10, 15, 20]
    }
    
    best_params = optimizer.grid_search(param_ranges)