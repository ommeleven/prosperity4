# backtest_algorithms.py
import json
import random
from datamodel import Order, OrderDepth, TradingState, Trade
from typing import Dict, List, Tuple
from collections import defaultdict
import copy

# Import your algorithms
from d_grid_search import Trader as GridSearchTrader
from d_mean_reversion import Trader as MeanReversionTrader

class MarketSimulator:
    """Simulates the IMC Prosperity market"""
    
    def __init__(self):
        self.products = ['ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT']
        self.position_limits = {'ASH_COATED_OSMIUM': 80, 'INTARIAN_PEPPER_ROOT': 80}
        self.transaction_fee = 0.01  # 1% fee as per IMC rules
        self.current_time = 0
        
    def generate_market_data(self, timestep: int) -> Dict[str, OrderDepth]:
        """
        Generate realistic market data based on IMC Prosperity patterns
        This simulates the hidden patterns in the real competition
        """
        order_depths = {}
        
        for product in self.products:
            # Base price pattern (hidden pattern like in real competition)
            if product == 'ASH_COATED_OSMIUM':
                # More volatile with hidden cyclical pattern
                base_price = 10000 + 50 * math.sin(timestep * 0.1) + 30 * math.sin(timestep * 0.37)
                volatility = 15
            else:  # INTARIAN_PEPPER_ROOT
                # Stable but with slight drift
                base_price = 5000 + 5 * math.sin(timestep * 0.05)
                volatility = 5
            
            # Add random noise
            true_price = base_price + random.gauss(0, volatility)
            
            # Create order depth (bid and ask orders)
            buy_orders = {}
            sell_orders = {}
            
            # Market maker provides liquidity at different price levels
            # Level 1: Best bid/ask (large volume - market maker)
            buy_orders[int(true_price - 1)] = 15
            sell_orders[int(true_price + 1)] = 15
            
            # Level 2: Slightly worse prices (smaller volume)
            buy_orders[int(true_price - 2)] = 10
            sell_orders[int(true_price + 2)] = 10
            
            # Level 3: Even worse (retail orders)
            buy_orders[int(true_price - 3)] = 5
            sell_orders[int(true_price + 3)] = 5
            
            # Occasional arbitrage opportunities
            if timestep % 20 == 0:  # Every 20 timesteps
                if random.random() > 0.5:
                    # Mispricing: Someone wants to buy above fair value
                    buy_orders[int(true_price + 8)] = 8
                else:
                    # Mispricing: Someone wants to sell below fair value
                    sell_orders[int(true_price - 8)] = 8
            
            order_depths[product] = OrderDepth()
            order_depths[product].buy_orders = buy_orders
            order_depths[product].sell_orders = sell_orders
        
        return order_depths
    
    def execute_orders(self, orders: List[Order], order_depth: OrderDepth, position: int, product: str) -> Tuple[List[Trade], int, float]:
        """
        Execute orders against market depth
        Returns: (trades, new_position, profit_delta)
        """
        trades = []
        current_position = position
        
        # Separate buy and sell orders
        buy_orders = [o for o in orders if o.quantity > 0]
        sell_orders = [o for o in orders if o.quantity < 0]
        
        # Execute buy orders (against sell_orders in market)
        for buy_order in buy_orders:
            remaining_qty = buy_order.quantity
            # Sort sell orders by price (lowest first)
            sorted_sells = sorted(order_depth.sell_orders.items())
            
            for price, volume in sorted_sells:
                if price <= buy_order.price and remaining_qty > 0:
                    trade_qty = min(remaining_qty, volume)
                    trades.append(Trade(
                        symbol=product,
                        price=price,
                        quantity=trade_qty,
                        buyer='TRADER',
                        seller='MARKET'
                    ))
                    remaining_qty -= trade_qty
                    current_position += trade_qty
            
            if remaining_qty > 0:
                print(f"  Warning: Only filled {buy_order.quantity - remaining_qty}/{buy_order.quantity} of buy order")
        
        # Execute sell orders (against buy_orders in market)
        for sell_order in sell_orders:
            remaining_qty = -sell_order.quantity
            # Sort buy orders by price (highest first)
            sorted_buys = sorted(order_depth.buy_orders.items(), reverse=True)
            
            for price, volume in sorted_buys:
                if price >= sell_order.price and remaining_qty > 0:
                    trade_qty = min(remaining_qty, volume)
                    trades.append(Trade(
                        symbol=product,
                        price=price,
                        quantity=-trade_qty,
                        buyer='MARKET',
                        seller='TRADER'
                    ))
                    remaining_qty -= trade_qty
                    current_position -= trade_qty
            
            if remaining_qty > 0:
                print(f"  Warning: Only filled {(-sell_order.quantity) - remaining_qty}/{-sell_order.quantity} of sell order")
        
        return trades, current_position
    
    def calculate_profit(self, trades: List[Trade], previous_trades: List[Trade]) -> float:
        """Calculate P&L from trades"""
        total_profit = 0.0
        
        for trade in trades:
            # Simple profit calculation (without inventory tracking for simplicity)
            if trade.quantity > 0:  # Bought
                total_profit -= trade.price * trade.quantity
            else:  # Sold
                total_profit += trade.price * (-trade.quantity)
        
        return total_profit

class BacktestEngine:
    def __init__(self, trader_instance, num_timesteps=100):
        self.trader = trader_instance
        self.num_timesteps = num_timesteps
        self.simulator = MarketSimulator()
        self.state = TradingState(
            timestamp=0,
            listings={},
            order_depths={},
            own_trades={},
            market_trades={},
            position={},
            observations={}
        )
        self.all_trades = []
        self.profit_history = []
        self.position_history = defaultdict(list)
        
    def run(self) -> Dict:
        """Run backtest"""
        total_profit = 0.0
        
        print(f"\n{'='*60}")
        print(f"BACKTESTING: {self.trader.__class__.__name__}")
        print(f"{'='*60}")
        
        for timestep in range(self.num_timesteps):
            # Update timestamp
            self.state.timestamp = timestep
            
            # Generate market data
            self.state.order_depths = self.simulator.generate_market_data(timestep)
            
            # Get trader's orders
            try:
                result = self.trader.run(self.state)
                orders_dict = result if isinstance(result, dict) else result[0]
            except Exception as e:
                print(f"Error at timestep {timestep}: {e}")
                continue
            
            # Execute orders and track P&L
            step_profit = 0.0
            for product, orders in orders_dict.items():
                if product not in self.state.order_depths:
                    continue
                
                position = self.state.position.get(product, 0)
                trades, new_position, profit = self.simulator.execute_orders(
                    orders, 
                    self.state.order_depths[product],
                    position,
                    product
                )
                
                # Update state
                self.state.position[product] = new_position
                step_profit += profit
                
                # Record trades
                for trade in trades:
                    self.all_trades.append({
                        'timestep': timestep,
                        'product': product,
                        'price': trade.price,
                        'quantity': trade.quantity,
                        'profit': profit
                    })
                
                # Track position history
                self.position_history[product].append(new_position)
            
            total_profit += step_profit
            self.profit_history.append(total_profit)
            
            # Print progress every 10 timesteps
            if (timestep + 1) % 10 == 0:
                print(f"Timestep {timestep + 1}/{self.num_timesteps} - Profit: {total_profit:,.2f}")
        
        # Calculate metrics
        metrics = self.calculate_metrics(total_profit)
        return metrics
    
    def calculate_metrics(self, total_profit: float) -> Dict:
        """Calculate performance metrics"""
        
        # Trade statistics
        total_trades = len(self.all_trades)
        buy_trades = sum(1 for t in self.all_trades if t['quantity'] > 0)
        sell_trades = total_trades - buy_trades
        
        # Profit per product
        profit_by_product = defaultdict(float)
        for trade in self.all_trades:
            profit_by_product[trade['product']] += trade['profit']
        
        # Win rate (simplified - assuming trades with price improvement)
        # In real scenario, you'd track actual P&L per trade
        
        # Maximum drawdown
        max_drawdown = 0
        peak = self.profit_history[0] if self.profit_history else 0
        for profit in self.profit_history:
            if profit > peak:
                peak = profit
            drawdown = peak - profit
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Final positions
        final_positions = dict(self.state.position)
        
        # Check if target reached
        target_reached = total_profit >= 200000
        
        metrics = {
            'total_profit': total_profit,
            'target_reached': target_profit,
            'target_reached': target_reached,
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'profit_by_product': dict(profit_by_product),
            'max_drawdown': max_drawdown,
            'final_positions': final_positions,
            'avg_profit_per_trade': total_profit / total_trades if total_trades > 0 else 0,
            'timesteps_completed': len(self.profit_history)
        }
        
        return metrics
    
    def print_report(self, metrics: Dict):
        """Print detailed performance report"""
        print(f"\n{'='*60}")
        print(f"PERFORMANCE REPORT")
        print(f"{'='*60}")
        
        # Target status
        if metrics['target_reached']:
            print(f"✅ TARGET ACHIEVED: {metrics['total_profit']:,.2f} / 200,000 XIRECs")
        else:
            print(f"❌ TARGET NOT ACHIEVED: {metrics['total_profit']:,.2f} / 200,000 XIRECs")
            print(f"   Shortfall: {200000 - metrics['total_profit']:,.2f} XIRECs")
        
        print(f"\n📊 TRADING STATISTICS:")
        print(f"   Total Profit: {metrics['total_profit']:,.2f} XIRECs")
        print(f"   Total Trades: {metrics['total_trades']}")
        print(f"   Buy Trades: {metrics['buy_trades']}")
        print(f"   Sell Trades: {metrics['sell_trades']}")
        print(f"   Avg Profit/Trade: {metrics['avg_profit_per_trade']:.2f}")
        
        print(f"\n💰 PROFIT BY PRODUCT:")
        for product, profit in metrics['profit_by_product'].items():
            print(f"   {product}: {profit:,.2f} XIRECs")
        
        print(f"\n⚠️  RISK METRICS:")
        print(f"   Max Drawdown: {metrics['max_drawdown']:,.2f} XIRECs")
        print(f"   Final Positions: {metrics['final_positions']}")
        
        print(f"\n📈 PERFORMANCE RATING:")
        if metrics['total_profit'] >= 200000:
            print("   🏆 EXCELLENT - Ready for competition!")
        elif metrics['total_profit'] >= 150000:
            print("   👍 GOOD - Needs minor optimization")
        elif metrics['total_profit'] >= 100000:
            print("   ⚠️  AVERAGE - Needs parameter tuning")
        else:
            print("   ❌ POOR - Strategy needs major revision")
        
        return metrics

def compare_algorithms():
    """Compare both algorithms side by side"""
    
    print("\n" + "="*70)
    print("COMPARING BOTH TRADING ALGORITHMS")
    print("="*70)
    
    # Test Grid Search Algorithm
    print("\n🚀 Testing Grid Search Algorithm...")
    grid_trader = GridSearchTrader()
    grid_engine = BacktestEngine(grid_trader, num_timesteps=100)
    grid_metrics = grid_engine.run()
    grid_engine.print_report(grid_metrics)
    
    # Test Mean Reversion Algorithm
    print("\n🚀 Testing Mean Reversion Algorithm...")
    mean_trader = MeanReversionTrader()
    mean_engine = BacktestEngine(mean_trader, num_timesteps=100)
    mean_metrics = mean_engine.run()
    mean_engine.print_report(mean_metrics)
    
    # Comparison summary
    print("\n" + "="*70)
    print("FINAL COMPARISON")
    print("="*70)
    print(f"{'Metric':<30} {'Grid Search':<20} {'Mean Reversion':<20}")
    print("-"*70)
    print(f"{'Total Profit (XIRECs)':<30} {grid_metrics['total_profit']:>19,.2f} {mean_metrics['total_profit']:>19,.2f}")
    print(f"{'Target Achieved':<30} {'✅' if grid_metrics['target_reached'] else '❌':<20} {'✅' if mean_metrics['target_reached'] else '❌':<20}")
    print(f"{'Total Trades':<30} {grid_metrics['total_trades']:>19} {mean_metrics['total_trades']:>19}")
    print(f"{'Max Drawdown':<30} {grid_metrics['max_drawdown']:>19,.2f} {mean_metrics['max_drawdown']:>19,.2f}")
    
    # Recommendation
    if grid_metrics['total_profit'] > mean_metrics['total_profit']:
        print("\n🏆 RECOMMENDATION: Use GRID SEARCH algorithm for competition")
        print(f"   Outperforms Mean Reversion by {grid_metrics['total_profit'] - mean_metrics['total_profit']:,.2f} XIRECs")
    else:
        print("\n🏆 RECOMMENDATION: Use MEAN REVERSION algorithm for competition")
        print(f"   Outperforms Grid Search by {mean_metrics['total_profit'] - grid_metrics['total_profit']:,.2f} XIRECs")
    
    return grid_metrics, mean_metrics

def test_single_algorithm(algorithm_name='grid_search', timesteps=50):
    """Test a single algorithm with custom parameters"""
    
    if algorithm_name == 'grid_search':
        trader = GridSearchTrader()
    elif algorithm_name == 'mean_reversion':
        trader = MeanReversionTrader()
    else:
        raise ValueError("Algorithm must be 'grid_search' or 'mean_reversion'")
    
    engine = BacktestEngine(trader, num_timesteps=timesteps)
    metrics = engine.run()
    engine.print_report(metrics)
    
    return metrics

if __name__ == "__main__":
    import math  # For market simulation
    
    print("IMC PROSPERITY - ALGORITHM BACKTESTING SUITE")
    print("="*70)
    print("\nChoose an option:")
    print("1. Compare both algorithms")
    print("2. Test Grid Search only")
    print("3. Test Mean Reversion only")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == '1':
        compare_algorithms()
    elif choice == '2':
        timesteps = int(input("Number of timesteps to simulate (default 50): ") or "50")
        test_single_algorithm('grid_search', timesteps)
    elif choice == '3':
        timesteps = int(input("Number of timesteps to simulate (default 50): ") or "50")
        test_single_algorithm('mean_reversion', timesteps)
    else:
        print("Invalid choice, running comparison by default...")
        compare_algorithms()