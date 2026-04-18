# analyze_trading_logs.py
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import seaborn as sns

class TradingLogAnalyzer:
    def __init__(self, json_file_path):
        with open(json_file_path, 'r') as f:
            self.data = json.load(f)
        self.trades = []
        self.orders = []
        self.positions = []
        self.parse_logs()
    
    def parse_logs(self):
        """Parse different JSON structures common in IMC logs"""
        if isinstance(self.data, dict):
            # Case 1: Dictionary with timestep keys
            if 'trades' in self.data:
                self.trades = self.data['trades']
            if 'orders' in self.data:
                self.orders = self.data['orders']
            if 'positions' in self.data:
                self.positions = self.data['positions']
            
            # Case 2: Time series data
            for key, value in self.data.items():
                if key.isdigit() or 'timestep' in key.lower():
                    self.process_timestep(value)
    
    def process_timestep(self, timestep_data):
        """Extract trading data from timestep"""
        if 'my_trades' in timestep_data:
            self.trades.extend(timestep_data['my_trades'])
        if 'order_depths' in timestep_data:
            self.orders.append(timestep_data['order_depths'])
    
    def calculate_metrics(self):
        """Calculate key performance metrics"""
        metrics = {}
        
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            
            # Basic metrics
            metrics['total_trades'] = len(trades_df)
            metrics['total_volume'] = trades_df['quantity'].abs().sum() if 'quantity' in trades_df else 0
            
            # P&L by product
            if 'profit' in trades_df:
                metrics['total_profit'] = trades_df['profit'].sum()
                metrics['profit_by_product'] = trades_df.groupby('product')['profit'].sum().to_dict()
            
            # Trade statistics
            if 'price' in trades_df:
                metrics['avg_trade_price'] = trades_df['price'].mean()
                metrics['price_volatility'] = trades_df['price'].std()
            
            # Buy vs Sell analysis
            if 'quantity' in trades_df:
                metrics['total_buys'] = trades_df[trades_df['quantity'] > 0]['quantity'].sum()
                metrics['total_sells'] = abs(trades_df[trades_df['quantity'] < 0]['quantity'].sum())
                metrics['net_position'] = metrics['total_buys'] - metrics['total_sells']
        
        return metrics
    
    def analyze_order_fill_rate(self):
        """Calculate what percentage of orders got filled"""
        if not self.orders:
            return {}
        
        total_orders = 0
        filled_orders = 0
        
        for order in self.orders:
            if isinstance(order, dict):
                for product, orders_list in order.items():
                    if isinstance(orders_list, list):
                        for single_order in orders_list:
                            total_orders += 1
                            if single_order.get('filled', False) or single_order.get('status') == 'FILLED':
                                filled_orders += 1
        
        return {
            'total_orders_placed': total_orders,
            'orders_filled': filled_orders,
            'fill_rate': filled_orders / total_orders if total_orders > 0 else 0
        }
    
    def detect_profit_opportunities(self):
        """Find moments where spread was exploitable"""
        opportunities = []
        
        for timestep in self.data.get('order_depths', []):
            if isinstance(timestep, dict):
                for product, depth in timestep.items():
                    if 'buy_orders' in depth and 'sell_orders' in depth:
                        best_bid = max(depth['buy_orders'].keys()) if depth['buy_orders'] else None
                        best_ask = min(depth['sell_orders'].keys()) if depth['sell_orders'] else None
                        
                        if best_bid and best_ask:
                            spread = best_ask - best_bid
                            if spread > 5:  # Arbitrage opportunity threshold
                                opportunities.append({
                                    'product': product,
                                    'spread': spread,
                                    'best_bid': best_bid,
                                    'best_ask': best_ask,
                                    'profit_potential': spread - 1  # After fees
                                })
        
        return opportunities
    
    def generate_report(self):
        """Generate comprehensive analysis report"""
        metrics = self.calculate_metrics()
        fill_metrics = self.analyze_order_fill_rate()
        opportunities = self.detect_profit_opportunities()
        
        print("=" * 60)
        print("TRADING ALGORITHM PERFORMANCE REPORT")
        print("=" * 60)
        
        print("\n📊 BASIC METRICS:")
        print(f"  Total Trades Executed: {metrics.get('total_trades', 0)}")
        print(f"  Total Volume Traded: {metrics.get('total_volume', 0)}")
        print(f"  Total Profit: {metrics.get('total_profit', 0):,.2f} XIRECs")
        
        if metrics.get('profit_by_product'):
            print("\n  Profit by Product:")
            for product, profit in metrics['profit_by_product'].items():
                print(f"    {product}: {profit:,.2f} XIRECs")
        
        print("\n📈 ORDER EXECUTION:")
        print(f"  Orders Placed: {fill_metrics.get('total_orders_placed', 0)}")
        print(f"  Orders Filled: {fill_metrics.get('orders_filled', 0)}")
        print(f"  Fill Rate: {fill_metrics.get('fill_rate', 0)*100:.1f}%")
        
        print("\n💰 PROFIT OPPORTUNITIES DETECTED:")
        print(f"  Exploitable Spreads Found: {len(opportunities)}")
        if opportunities:
            avg_spread = np.mean([opp['spread'] for opp in opportunities])
            print(f"  Average Exploitable Spread: {avg_spread:.2f}")
        
        print("\n⚠️  RECOMMENDATIONS:")
        if fill_metrics.get('fill_rate', 0) < 0.5:
            print("  • Low fill rate - Consider placing orders closer to market prices")
        if metrics.get('total_trades', 0) < 50:
            print("  • Low trading volume - Increase order quantities or reduce spreads")
        if metrics.get('total_profit', 0) < 200000:
            print(f"  • Need {200000 - metrics.get('total_profit', 0):,.0f} more XIRECs to reach target")
            print("  • Consider more aggressive market taking on spreads > 3")
        
        return metrics, fill_metrics, opportunities

# Usage
if __name__ == "__main__":
    analyzer = TradingLogAnalyzer('/Users/HP/src/prosperity4/performance metrics/d_cons_MM_log/177180.json')
    analyzer.generate_report()