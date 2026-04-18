# parse_trading_logs.py
import re
import json
from pathlib import Path
from typing import Dict, List, Any

class UniversalLogParser:
    """Parse logs from various IMC Prosperity formats"""
    
    @staticmethod
    def parse_json_log(file_path: str) -> Dict:
        """Parse JSON format logs"""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def parse_text_log(file_path: str) -> List[Dict]:
        """Parse plain text logs"""
        trades = []
        pattern = r'(\w+)\s+(?:bought|sold)\s+(\d+)\s+@\s+(\d+(?:\.\d+)?)\s+profit:\s+(-?\d+(?:\.\d+)?)'
        
        with open(file_path, 'r') as f:
            for line in f:
                match = re.search(pattern, line)
                if match:
                    trades.append({
                        'product': match.group(1),
                        'quantity': int(match.group(2)) if 'bought' in line else -int(match.group(2)),
                        'price': float(match.group(3)),
                        'profit': float(match.group(4))
                    })
        return trades
    
    @staticmethod
    def parse_py_logs(file_path: str) -> Dict:
        """Extract logs from Python file print statements"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract print statements that look like logging
        log_pattern = r'print\s*\(.*?profit.*?\)'
        logs = re.findall(log_pattern, content, re.IGNORECASE)
        
        return {'extracted_logs': logs, 'total_lines': len(logs)}
    
    @staticmethod
    def auto_detect_and_parse(directory: str) -> Dict[str, Any]:
        """Auto-detect log files in directory and parse them"""
        results = {}
        path = Path(directory)
        
        for file_path in path.glob('*'):
            if file_path.suffix == '.json':
                results['json'] = UniversalLogParser.parse_json_log(file_path)
            elif file_path.suffix == '.log':
                results['log'] = UniversalLogParser.parse_text_log(file_path)
            elif file_path.suffix == '.py':
                results['py'] = UniversalLogParser.parse_py_logs(file_path)
        
        return results
    
    @staticmethod
    def generate_summary(parsed_data: Dict) -> None:
        """Generate summary from parsed logs"""
        total_profit = 0
        all_trades = []
        
        # Extract trades from different formats
        if 'log' in parsed_data and isinstance(parsed_data['log'], list):
            all_trades.extend(parsed_data['log'])
        
        if 'json' in parsed_data:
            json_data = parsed_data['json']
            if 'trades' in json_data:
                all_trades.extend(json_data['trades'])
            elif 'profit' in json_data:
                total_profit = json_data['profit']
        
        # Calculate metrics
        if all_trades:
            total_profit = sum(t.get('profit', 0) for t in all_trades)
            total_volume = sum(abs(t.get('quantity', 0)) for t in all_trades)
            
            print("\n📊 LOG ANALYSIS SUMMARY")
            print("="*50)
            print(f"Total Profit: {total_profit:,.2f} XIRECs")
            print(f"Total Volume: {total_volume}")
            print(f"Total Trades: {len(all_trades)}")
            
            if total_volume > 0:
                avg_price = sum(t.get('price', 0) * abs(t.get('quantity', 0)) for t in all_trades) / total_volume
                print(f"Average Price: {avg_price:.2f}")
        
        if 'py' in parsed_data:
            print(f"\n📝 Python File Stats:")
            print(f"  Log statements found: {parsed_data['py'].get('total_lines', 0)}")
        
        return total_profit

# Usage
if __name__ == "__main__":
    # Parse all logs in current directory
    parser = UniversalLogParser()
    results = parser.auto_detect_and_parse('.')
    parser.generate_summary(results)