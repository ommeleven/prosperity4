import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 1. Data Preparation: Combine all 3 days into a continuous timeline
def load_and_combine_data():
    files = ['algs/r3/prices_round_3_day_0.csv', 'algs/r3/prices_round_3_day_1.csv', 'algs/r3/prices_round_3_day_2.csv']
    dfs = []
    for i, f in enumerate(files):
        df_temp = pd.read_csv(f, sep=';')
        # Offset timestamp to make days continuous (1,000,000 units per day)
        df_temp['timestamp'] += i * 1000000
        dfs.append(df_temp)
    return pd.concat(dfs)

df = load_and_combine_data()
vfe_df = df[df['product'] == 'VELVETFRUIT_EXTRACT'].set_index('timestamp')

# 2. Meaningful Plotting
def create_plots(df, vfe_df):
    # Plot 1: Hydrogel Pack Price
    hp = df[df['product'] == 'HYDROGEL_PACK']
    plt.figure(figsize=(12, 5))
    plt.plot(hp['timestamp'], hp['mid_price'], label='HYDROGEL_PACK', color='blue')
    plt.title('HYDROGEL_PACK Price History')
    plt.xlabel('Cumulative Timestamp')
    plt.ylabel('Price')
    plt.grid(True, alpha=0.3)
    plt.savefig('hydrogel_price.png')

    # Plot 2: Underlying vs Vouchers
    plt.figure(figsize=(12, 6))
    plt.plot(vfe_df.index, vfe_df['mid_price'], label='Underlying (Extract)', color='orange', linewidth=2)
    
    # Selecting a few representative strikes
    for strike in [5000, 5200, 5400]:
        v_data = df[df['product'] == f'VEV_{strike}']
        plt.plot(v_data['timestamp'], v_data['mid_price'], label=f'Voucher K={strike}', alpha=0.8)
    
    plt.title('Relationship: Extract vs Voucher Prices')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig('extract_vs_vouchers.png')

# 3. Relationship Analysis (Options Math)
def analyze_vouchers(df, vfe_df):
    voucher_names = [p for p in df['product'].unique() if 'VEV_' in p]
    stats = []

    for name in voucher_names:
        strike = int(name.split('_')[1])
        v_data = df[df['product'] == name].set_index('timestamp')
        
        # Align timestamps
        common_idx = vfe_df.index.intersection(v_data.index)
        S = vfe_df.loc[common_idx, 'mid_price']
        V = v_data.loc[common_idx, 'mid_price']
        
        # Calculate Option Metrics
        intrinsic = np.maximum(S - strike, 0)
        extrinsic = V - intrinsic
        delta, _ = np.polyfit(S, V, 1) # Linear slope is an estimate for Delta
        
        stats.append({
            'Product': name,
            'Strike': strike,
            'Avg_Extrinsic': extrinsic.mean(),
            'Estimated_Delta': delta,
            'Correlation': S.corr(V)
        })

    results = pd.DataFrame(stats).sort_values('Strike')
    print("\n--- Voucher Analysis Results ---")
    print(results[['Product', 'Strike', 'Estimated_Delta', 'Avg_Extrinsic', 'Correlation']])
    
    # Plot Extrinsic Value Curve
    plt.figure(figsize=(10, 5))
    plt.bar(results['Strike'].astype(str), results['Avg_Extrinsic'], color='teal')
    plt.title('Extrinsic Value (Time Value) across Strike Prices')
    plt.ylabel('Value')
    plt.xlabel('Strike Price')
    plt.savefig('extrinsic_curve.png')

# Run Analysis
create_plots(df, vfe_df)
analyze_vouchers(df, vfe_df)