import os
import pandas as pd

# Folder = current directory
folder_path = os.path.dirname(os.path.abspath(__file__))

# Find all CSV files
csv_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

# Sort for consistency
csv_files.sort()

print(f"Found {len(csv_files)} CSV files\n")

for file in csv_files:
    file_path = os.path.join(folder_path, file)
    
    print("=" * 80)
    print(f"FILE: {file}")
    print("=" * 80)
    
    try:
        df = pd.read_csv(file_path)
        
        # Basic info
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}\n")
        
        # Head
        print("HEAD (first 5 rows):")
        print(df.head(), "\n")
        
        # Tail
        print("TAIL (last 5 rows):")
        print(df.tail(), "\n")
        
        # Random sample (if large enough)
        if len(df) > 10:
            print("RANDOM SAMPLE (5 rows):")
            print(df.sample(5), "\n")
    
    except Exception as e:
        print(f"Error reading {file}: {e}")

print("\nDone.")