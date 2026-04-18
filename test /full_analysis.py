# run_full_analysis.py
import sys
import json
from pathlib import Path

def run_complete_analysis(log_directory='.'):
    """Run all analysis scripts on your logs"""
    
    print("🚀 Starting Complete Trading Analysis")
    print("="*60)
    
    # Step 1: Parse all logs
    print("\n📁 Parsing log files...")
    parser = UniversalLogParser()
    parsed_data = parser.auto_detect_and_parse(log_directory)
    total_profit = parser.generate_summary(parsed_data)
    
    # Step 2: Deep analysis if JSON found
    if 'json' in parsed_data:
        print("\n📊 Running detailed performance analysis...")
        analyzer = TradingLogAnalyzer(parsed_data['json'])
        metrics, fill_metrics, opportunities = analyzer.generate_report()
        
        # Step 3: Generate improvements
        print("\n🔧 Generating improvement recommendations...")
        combined_metrics = {
            'total_profit': total_profit,
            'total_volume': metrics.get('total_volume', 0),
            'win_rate': metrics.get('win_rate', 0),
            'net_position': metrics.get('net_position', 0),
            'avg_spread_captured': np.mean([opp['spread'] for opp in opportunities]) if opportunities else 0
        }
        
        improver = StrategyImprover(combined_metrics)
        improver.print_report()
    
    print("\n Analysis complete! Implement recommendations to improve performance.")

if __name__ == "__main__":
    # Run on current directory
    run_complete_analysis('.')