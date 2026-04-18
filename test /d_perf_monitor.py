# performance_monitor.py
import time
import json
from collections import deque
import numpy as np

class PerformanceMonitor:
    def __init__(self, target_profit=200000):
        self.target_profit = target_profit
        self.trade_history = deque(maxlen=1000)
        self.position_history = {}
        self.profit_history = []
        self.start_time = time.time()
        
    def log_trade(self, product, price, quantity, profit):
        """Record each trade"""
        self.trade_history.append({
            'timestamp': time.time(),
            'product': product,
            'price': price,
            'quantity': quantity,
            'profit': profit
        })
        
        # Update position
        if product not in self.position_history:
            self.position_history[product] = 0
        self.position_history[product] += quantity
        
        # Update running profit
        if self.profit_history:
            new_profit = self.profit_history[-1] + profit
        else:
            new_profit = profit
        self.profit_history.append(new_profit)
    
    def get_current_status(self):
        """Get real-time performance metrics"""
        elapsed_time = time.time() - self.start_time
        current_profit = self.profit_history[-1] if self.profit_history else 0
        progress_pct = (current_profit / self.target_profit) * 100
        
        # Calculate win rate
        if len(self.trade_history) > 0:
            winning_trades = sum(1 for t in self.trade_history if t['profit'] > 0)
            win_rate = winning_trades / len(self.trade_history)
        else:
            win_rate = 0
        
        # Calculate Sharpe ratio (simplified)
        if len(self.profit_history) > 1:
            returns = np.diff(self.profit_history)
            sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252)
        else:
            sharpe = 0
        
        return {
            'current_profit': current_profit,
            'target_remaining': self.target_profit - current_profit,
            'progress': progress_pct,
            'total_trades': len(self.trade_history),
            'win_rate': win_rate * 100,
            'sharpe_ratio': sharpe,
            'positions': dict(self.position_history),
            'elapsed_minutes': elapsed_time / 60
        }
    
    def display_dashboard(self):
        """Print real-time dashboard"""
        status = self.get_current_status()
        
        print("\n" + "="*60)
        print(f"📈 TRADING DASHBOARD - {time.strftime('%H:%M:%S')}")
        print("="*60)
        print(f"Profit: {status['current_profit']:,.2f} / {self.target_profit:,.2f} XIRECs")
        print(f"Progress: {'█' * int(status['progress']/5)}{'░' * (20 - int(status['progress']/5))} {status['progress']:.1f}%")
        print(f"Remaining: {status['target_remaining']:,.2f} XIRECs")
        print(f"\nTrades: {status['total_trades']} | Win Rate: {status['win_rate']:.1f}%")
        print(f"Sharpe: {status['sharpe_ratio']:.2f} | Time: {status['elapsed_minutes']:.1f} min")
        print(f"\nPositions:")
        for product, pos in status['positions'].items():
            print(f"  {product}: {pos}")
        
        # Alert if off track
        minutes_remaining = 72 * 60 - status['elapsed_minutes']  # 72 hour trading day
        required_rate = status['target_remaining'] / max(minutes_remaining, 1)
        
        if required_rate > 1000:  # Need >1000 XIREC per minute
            print(f"\n⚠️  ALERT: Need {required_rate:.0f} XIREC/minute to reach target!")
            print("   Consider increasing position sizes or reducing spreads")
        
        return status
    
    def should_adjust_strategy(self):
        """Determine if strategy needs adjustment"""
        status = self.get_current_status()
        
        adjustments_needed = []
        
        if status['win_rate'] < 40:
            adjustments_needed.append("Low win rate - reduce spread or improve fair value estimation")
        
        if status['sharpe_ratio'] < 0.5 and status['total_trades'] > 20:
            adjustments_needed.append("Poor risk-adjusted returns - consider wider spreads")
        
        if status['progress'] < 50 and status['elapsed_minutes'] > 60:
            adjustments_needed.append("Behind target - increase aggression or add market taking")
        
        return adjustments_needed

# Monitor in real-time during trading
monitor = PerformanceMonitor(target_profit=200000)

# Call this after each trade in your main algorithm
# monitor.log_trade(product, price, quantity, profit)
# status = monitor.display_dashboard()