import numpy as np
import pandas as pd
from scipy.stats import norm
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class OptionData:
    product: str
    bid: float
    ask: float
    kind: str
    K: float  # Strike price
    Tw: float  # Time to expiry in weeks

# Market parameters
S0 = 50.0  # Current spot price of AETHER_CRYSTAL (mid of bid/ask)
SIGMA = 2.51  # 251% annualized volatility
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY
R = 0.0  # Risk-free rate (zero drift mentioned)
NUM_SIMULATIONS = 100

# Exotic option parameters
BINARY_PAYOUT = 10.0  # Binary put pays this amount
KO_BARRIER = 35.0  # Knock-out barrier
CHOOSER_DECISION_TIME = 2  # Weeks when chooser decides (for 3-week option)

def weeks_to_years(weeks: float) -> float:
    """Convert weeks to years using 5 trading days per week"""
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def weeks_to_steps(weeks: float) -> int:
    """Convert weeks to simulation steps"""
    return int(round(weeks * 5 * STEPS_PER_DAY))

def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes call option price"""
    if T <= 0:
        return max(S - K, 0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return call

def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes put option price"""
    if T <= 0:
        return max(K - S, 0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    put = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return put

def monte_carlo_european_call(S: float, K: float, T: float, r: float, sigma: float, 
                             num_sims: int = NUM_SIMULATIONS) -> float:
    """Monte Carlo pricing for European call option"""
    dt = T / weeks_to_steps(weeks_to_years(T) * TRADING_DAYS_PER_YEAR / 5)
    steps = weeks_to_steps(weeks_to_years(T) * TRADING_DAYS_PER_YEAR / 5)
    
    payoffs = []
    np.random.seed(42)
    
    for _ in range(num_sims):
        S_t = S
        for _ in range(steps):
            Z = np.random.standard_normal()
            S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
        payoffs.append(max(S_t - K, 0))
    
    price = np.exp(-r * T) * np.mean(payoffs)
    return price

def monte_carlo_european_put(S: float, K: float, T: float, r: float, sigma: float,
                            num_sims: int = NUM_SIMULATIONS) -> float:
    """Monte Carlo pricing for European put option"""
    steps = weeks_to_steps(T)
    dt = T / steps if steps > 0 else 1e-4
    
    payoffs = []
    np.random.seed(42)
    
    for _ in range(num_sims):
        S_t = S
        for _ in range(steps):
            Z = np.random.standard_normal()
            S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
        payoffs.append(max(K - S_t, 0))
    
    price = np.exp(-r * T) * np.mean(payoffs)
    return price

def monte_carlo_chooser(S: float, K: float, T_total: float, T_decision: float, 
                       r: float, sigma: float, num_sims: int = NUM_SIMULATIONS) -> float:
    """
    Monte Carlo for Chooser option.
    At T_decision, the buyer chooses PUT or CALL (whichever is ITM).
    Then it runs until T_total expiry.
    """
    steps_total = weeks_to_steps(T_total)
    steps_decision = weeks_to_steps(T_decision)
    dt = T_total / steps_total if steps_total > 0 else 1e-4
    
    payoffs = []
    np.random.seed(42)
    
    for _ in range(num_sims):
        path = [S]
        S_t = S
        
        # Simulate to decision time
        for i in range(steps_decision):
            Z = np.random.standard_normal()
            S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
            path.append(S_t)
        
        S_decision = path[-1]
        
        # Choose the side that is in the money at decision time
        call_value = S_decision - K
        put_value = K - S_decision
        
        if call_value > put_value:
            # Choose call: continue simulating from decision to expiry
            S_t = S_decision
            for i in range(steps_total - steps_decision):
                Z = np.random.standard_normal()
                S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
            payoff = max(S_t - K, 0)
        else:
            # Choose put: continue simulating from decision to expiry
            S_t = S_decision
            for i in range(steps_total - steps_decision):
                Z = np.random.standard_normal()
                S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
            payoff = max(K - S_t, 0)
        
        payoffs.append(payoff)
    
    price = np.exp(-r * T_total) * np.mean(payoffs)
    return price

def monte_carlo_binary_put(S: float, K: float, T: float, r: float, sigma: float,
                          payout: float = BINARY_PAYOUT, num_sims: int = NUM_SIMULATIONS) -> float:
    """
    Monte Carlo for Binary Put option.
    Pays payout amount if S_T < K, otherwise worthless.
    """
    steps = weeks_to_steps(T)
    dt = T / steps if steps > 0 else 1e-4
    
    payoffs = []
    np.random.seed(42)
    
    for _ in range(num_sims):
        S_t = S
        for _ in range(steps):
            Z = np.random.standard_normal()
            S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
        payoff = payout if S_t < K else 0
        payoffs.append(payoff)
    
    price = np.exp(-r * T) * np.mean(payoffs)
    return price

def monte_carlo_knockout_put(S: float, K: float, barrier: float, T: float, r: float, 
                            sigma: float, num_sims: int = NUM_SIMULATIONS) -> float:
    """
    Monte Carlo for Knock-Out Put option.
    Becomes worthless if spot ever touches/crosses barrier.
    Otherwise pays max(K - S_T, 0) at expiry.
    """
    steps = weeks_to_steps(T)
    dt = T / steps if steps > 0 else 1e-4
    
    payoffs = []
    np.random.seed(42)
    
    for _ in range(num_sims):
        S_t = S
        knocked_out = False
        
        for _ in range(steps):
            Z = np.random.standard_normal()
            S_t = S_t * np.exp((r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
            
            # Check if barrier breached (down-and-out)
            if S_t < barrier:
                knocked_out = True
                break
        
        if knocked_out:
            payoff = 0
        else:
            payoff = max(K - S_t, 0)
        
        payoffs.append(payoff)
    
    price = np.exp(-r * T) * np.mean(payoffs)
    return price

def price_option(option: OptionData) -> float:
    """Price an option based on its type"""
    if option.kind == "underlying":
        return S0
    
    T = weeks_to_years(option.Tw)
    
    if option.kind == "call":
        # Use Black-Scholes for vanilla calls
        return black_scholes_call(S0, option.K, T, R, SIGMA)
    
    elif option.kind == "put":
        # Use Black-Scholes for vanilla puts
        return black_scholes_put(S0, option.K, T, R, SIGMA)
    
    elif option.kind == "chooser":
        T_decision = weeks_to_years(CHOOSER_DECISION_TIME)
        return monte_carlo_chooser(S0, option.K, T, T_decision, R, SIGMA)
    
    elif option.kind == "binary_put":
        return monte_carlo_binary_put(S0, option.K, T, R, SIGMA)
    
    elif option.kind == "knockout":
        return monte_carlo_knockout_put(S0, option.K, KO_BARRIER, T, R, SIGMA)
    
    else:
        raise ValueError(f"Unknown option kind: {option.kind}")

def analyze_option(option: OptionData) -> Dict:
    """Analyze an option and return pricing results"""
    mid = (option.bid + option.ask) / 2
    model_value = price_option(option)
    
    # Edge calculation
    edge_vs_mid = model_value - mid
    
    # Recommend side based on edge
    # Positive edge vs mid: model > mid, likely underpriced (BUY)
    # Negative edge vs mid: model < mid, likely overpriced (SELL)
    # Threshold: only recommend if edge > 0.01 (1 cent, accounting for spreads)
    
    threshold = 0.01
    
    if edge_vs_mid > threshold:
        recommended_side = "BUY"
        edge = edge_vs_mid
    elif edge_vs_mid < -threshold:
        recommended_side = "SELL"
        edge = -edge_vs_mid
    else:
        recommended_side = "NEUTRAL"
        edge = 0
    
    return {
        "product": option.product,
        "bid": option.bid,
        "ask": option.ask,
        "mid": mid,
        "model_value": model_value,
        "edge_vs_mid": edge_vs_mid,
        "edge_amount": edge,
        "recommended_side": recommended_side,
    }

def main():
    # Define products
    products = [
        OptionData("AC", 49.975, 50.025, "underlying", None, None),
        OptionData("AC_50_P", 12.000, 12.050, "put", 50, 3),
        OptionData("AC_50_C", 12.000, 12.050, "call", 50, 3),
        OptionData("AC_35_P", 4.330, 4.350, "put", 35, 3),
        OptionData("AC_40_P", 6.500, 6.550, "put", 40, 3),
        OptionData("AC_45_P", 9.050, 9.100, "put", 45, 3),
        OptionData("AC_60_C", 8.800, 8.850, "call", 60, 3),
        OptionData("AC_50_P_2", 9.700, 9.750, "put", 50, 2),
        OptionData("AC_50_C_2", 9.700, 9.750, "call", 50, 2),
        OptionData("AC_50_CO", 22.200, 22.300, "chooser", 50, 3),
        OptionData("AC_40_BP", 5.000, 5.100, "binary_put", 40, 3),
        OptionData("AC_45_KO", 0.150, 0.175, "knockout", 45, 3),
    ]
    
    print("=" * 120)
    print("OPTIONS PRICING ANALYSIS - AETHER CRYSTAL DERIVATIVES")
    print("=" * 120)
    print(f"\nMarket Parameters:")
    print(f"  Spot Price (S0): {S0}")
    print(f"  Volatility (σ): {SIGMA*100:.1f}%")
    print(f"  Risk-free rate (r): {R*100:.1f}%")
    print(f"  Trading days/year: {TRADING_DAYS_PER_YEAR}")
    print(f"  Simulations: {NUM_SIMULATIONS}")
    print()
    
    # Analyze each product
    results = []
    for product in products:
        result = analyze_option(product)
        results.append(result)
    
    # Create DataFrame for nice display
    df = pd.DataFrame(results)
    
    # Display main pricing table
    print("\nPRICING & RECOMMENDATION TABLE")
    print("=" * 120)
    display_df = df[["product", "bid", "ask", "mid", "model_value", "edge_vs_mid", "recommended_side"]].copy()
    display_df["bid"] = display_df["bid"].apply(lambda x: f"{x:.3f}")
    display_df["ask"] = display_df["ask"].apply(lambda x: f"{x:.3f}")
    display_df["mid"] = display_df["mid"].apply(lambda x: f"{x:.3f}")
    display_df["model_value"] = display_df["model_value"].apply(lambda x: f"{x:.3f}")
    display_df["edge_vs_mid"] = display_df["edge_vs_mid"].apply(lambda x: f"{x:+.3f}")
    
    print(display_df.to_string(index=False))
    
    # Summary statistics
    print("\n" + "=" * 120)
    print("EDGE ANALYSIS (Model vs Market Prices)")
    print("=" * 120)
    
    buy_opportunities = df[df["recommended_side"] == "BUY"].sort_values("edge_amount", ascending=False)
    sell_opportunities = df[df["recommended_side"] == "SELL"].sort_values("edge_amount", ascending=False)
    
    if len(buy_opportunities) > 0:
        print("\n📈 BUY OPPORTUNITIES (Model > Ask):")
        for _, row in buy_opportunities.iterrows():
            print(f"  {row['product']:12s} | Ask: {row['ask']:.3f} | Model: {row['model_value']:.3f} | Edge: {row['edge_amount']:+.3f}")
    
    if len(sell_opportunities) > 0:
        print("\n📉 SELL OPPORTUNITIES (Model < Bid):")
        for _, row in sell_opportunities.iterrows():
            print(f"  {row['product']:12s} | Bid: {row['bid']:.3f} | Model: {row['model_value']:.3f} | Edge: {row['edge_amount']:+.3f}")
    
    neutral = df[df["recommended_side"] == "NEUTRAL"]
    if len(neutral) > 0:
        print("\n⚖️  NEUTRAL (Fair Priced):")
        for _, row in neutral.iterrows():
            print(f"  {row['product']:12s} | Mid: {row['mid']:.3f} | Model: {row['model_value']:.3f}")
    
    # Detailed analysis by option type
    print("\n" + "=" * 120)
    print("DETAILED ANALYSIS BY OPTION TYPE")
    print("=" * 120)
    
    vanilla_puts = df[df["product"].str.contains("_P|_P_2") & ~df["product"].str.contains("BP|KO")]
    vanilla_calls = df[df["product"].str.contains("_C|_C_2") & ~df["product"].str.contains("CO")]
    exotics = df[df["product"].str.contains("CO|BP|KO")]
    
    print("\nVANILLA PUTS (3-week):")
    if len(vanilla_puts) > 0:
        for _, row in vanilla_puts.iterrows():
            print(f"  {row['product']:12s} K={row['product'].split('_')[1]:>3s} | Model: {row['model_value']:7.3f} | Mid: {row['mid']:7.3f} | Rec: {row['recommended_side']}")
    
    print("\nVANILLA CALLS (3-week):")
    if len(vanilla_calls) > 0:
        for _, row in vanilla_calls.iterrows():
            print(f"  {row['product']:12s} K={row['product'].split('_')[1]:>3s} | Model: {row['model_value']:7.3f} | Mid: {row['mid']:7.3f} | Rec: {row['recommended_side']}")
    
    print("\nEXOTIC OPTIONS:")
    if len(exotics) > 0:
        for _, row in exotics.iterrows():
            print(f"  {row['product']:12s} | Model: {row['model_value']:7.3f} | Mid: {row['mid']:7.3f} | Rec: {row['recommended_side']}")
    
    print("\n" + "=" * 120)

if __name__ == "__main__":
    main()