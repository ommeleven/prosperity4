# improvement_engine.py
import json


class StrategyImprover:
    def __init__(self, performance_metrics):
        self.metrics = performance_metrics
        self.recommendations = []
    
    def analyze_and_recommend(self):
        """Generate specific recommendations based on metrics"""
        
        # Profit shortfall analysis
        if self.metrics.get('total_profit', 0) < 200000:
            shortfall = 200000 - self.metrics['total_profit']
            self.recommendations.append({
                'priority': 'HIGH',
                'area': 'Profit Target',
                'action': f'Need {shortfall} more XIRECs',
                'suggestion': 'Increase position sizing or add mean reversion strategy'
            })
        
        # Volume analysis
        if self.metrics.get('total_volume', 0) < 1000:
            self.recommendations.append({
                'priority': 'HIGH',
                'area': 'Trading Volume',
                'action': 'Insufficient volume traded',
                'suggestion': 'Reduce bid-ask spread from 2 to 1 to increase fills'
            })
        
        # Win rate analysis
        if self.metrics.get('win_rate', 0) < 50:
            self.recommendations.append({
                'priority': 'MEDIUM',
                'area': 'Trade Quality',
                'action': f"Win rate {self.metrics['win_rate']:.1f}% is low",
                'suggestion': 'Widen spreads to 3-4 for better selectivity'
            })
        
        # Position management
        if abs(self.metrics.get('net_position', 0)) > 40:
            self.recommendations.append({
                'priority': 'HIGH',
                'area': 'Inventory Risk',
                'action': f"Large net position: {self.metrics['net_position']}",
                'suggestion': 'Add position-clearing logic when inventory > 60% of limit'
            })
        
        # Spread capture analysis
        if self.metrics.get('avg_spread_captured', 0) < 1:
            self.recommendations.append({
                'priority': 'MEDIUM',
                'area': 'Spread Capture',
                'action': 'Not capturing enough spread',
                'suggestion': 'Increase edge to 3 for volatile products like Osmium'
            })
        
        return self.recommendations
    
    def generate_improved_code_snippets(self):
        """Generate code snippets to fix identified issues"""
        snippets = []
        
        for rec in self.recommendations:
            if 'position' in rec['area'].lower():
                snippets.append("""
# Position clearing logic to add to your trader class
def clear_position(self, product: str, order_depth: OrderDepth, position: int):
    limit = 80
    if position > limit * 0.7:  # Too long
        best_bid = max(order_depth.buy_orders.keys())
        return [Order(product, best_bid, -position)]  # Liquidate
    elif position < -limit * 0.7:  # Too short
        best_ask = min(order_depth.sell_orders.keys())
        return [Order(product, best_ask, -position)]  # Cover
    return []
""")
            
            if 'spread' in rec['area'].lower() or 'edge' in rec['action'].lower():
                snippets.append("""
# Dynamic edge based on volatility
def calculate_dynamic_edge(self, product: str, order_depth: OrderDepth):
    # Calculate spread
    best_bid = max(order_depth.buy_orders.keys())
    best_ask = min(order_depth.sell_orders.keys())
    spread = best_ask - best_bid
    
    # Use wider edge for volatile Osmium
    if product == 'ASH_COATED_OSMIUM':
        return max(3, spread // 2)
    else:
        return max(1, spread // 3)
""")
        
        return snippets
    
    def print_report(self):
        """Print formatted improvement report"""
        print("\n" + "="*70)
        print("🔧 STRATEGY IMPROVEMENT RECOMMENDATIONS")
        print("="*70)
        
        for i, rec in enumerate(self.recommendations, 1):
            print(f"\n{i}. [{rec['priority']}] {rec['area']}")
            print(f"   Issue: {rec['action']}")
            print(f"   Fix: {rec['suggestion']}")
        
        snippets = self.generate_improved_code_snippets()
        if snippets:
            print("\n" + "="*70)
            print("📝 CODE IMPROVEMENTS TO IMPLEMENT")
            print("="*70)
            for snippet in snippets:
                print(snippet)
                print("-"*50)

# Usage
if __name__ == "__main__":
    # Load your metrics from JSON
    with open('/Users/HP/src/prosperity4/performance metrics/d_cons_MM_log/177180.json', 'r') as f:
        metrics = json.load(f)
    
    improver = StrategyImprover(metrics)
    improver.print_report()