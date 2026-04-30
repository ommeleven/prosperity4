import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import norm, skew, kurtosis
import seaborn as sns
from dataclasses import dataclass
from typing import List, Dict, Tuple

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

# ======================= PARAMETERS =======================
S0 = 50.0  # Current spot price
SIGMA = 2.51  # 251% annualized volatility
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY
R = 0.0  # Risk-free rate (zero drift)
NUM_SIMULATIONS = 1000
CONTRACT_SIZE = 3000  # PnL multiplier

# Exotic parameters
BINARY_PAYOUT = 10.0
KO_BARRIER = 35.0
CHOOSER_DECISION_TIME = 2  # weeks

def weeks_to_years(weeks: float) -> float:
    """Convert weeks to years"""
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def weeks_to_steps(weeks: float) -> int:
    """Convert weeks to simulation steps"""
    return int(round(weeks * 5 * STEPS_PER_DAY))

# ======================= PORTFOLIO DEFINITION =======================
@dataclass
class Position:
    """Represents a single position in the portfolio"""
    product: str
    entry_price: float  # What we paid/received
    quantity: float  # Number of contracts
    option_type: str  # 'call', 'put', 'chooser', 'binary_put', 'knockout', 'underlying'
    strike: float = None  # Strike price
    expiry_weeks: float = None  # Time to expiry
    is_short: bool = False  # True if short position
    barrier: float = None  # For knockout options
    decision_weeks: float = None  # For chooser options

class PortfolioSimulator:
    def __init__(self, positions: List[Position], num_simulations: int = NUM_SIMULATIONS):
        self.positions = positions
        self.num_simulations = num_simulations
        self.pnl_results = None
        self.price_paths = None
        
    def generate_price_paths(self, weeks_to_expiry: float) -> np.ndarray:
        """
        Generate GBM price paths for underlying
        Returns: (num_simulations, num_steps) array of prices
        """
        steps = weeks_to_steps(weeks_to_expiry)
        dt = weeks_to_years(weeks_to_expiry) / steps
        
        paths = np.zeros((self.num_simulations, steps + 1))
        paths[:, 0] = S0
        
        np.random.seed(42)
        
        for i in range(steps):
            Z = np.random.standard_normal(self.num_simulations)
            paths[:, i+1] = paths[:, i] * np.exp(
                (R - 0.5 * SIGMA**2) * dt + SIGMA * np.sqrt(dt) * Z
            )
        
        self.price_paths = paths
        return paths
    
    def payoff_call(self, S_final: np.ndarray, strike: float) -> np.ndarray:
        """European call payoff"""
        return np.maximum(S_final - strike, 0)
    
    def payoff_put(self, S_final: np.ndarray, strike: float) -> np.ndarray:
        """European put payoff"""
        return np.maximum(strike - S_final, 0)
    
    def payoff_chooser(self, paths: np.ndarray, strike: float, 
                       decision_weeks: float) -> np.ndarray:
        """Chooser option payoff - at decision time, choose PUT or CALL (ITM)"""
        decision_steps = weeks_to_steps(decision_weeks)
        S_decision = paths[:, decision_steps]
        S_final = paths[:, -1]
        
        payoffs = np.zeros(self.num_simulations)
        
        for i in range(self.num_simulations):
            call_value = S_decision[i] - strike
            put_value = strike - S_decision[i]
            
            if call_value > put_value:
                # Choose call
                payoffs[i] = np.maximum(S_final[i] - strike, 0)
            else:
                # Choose put
                payoffs[i] = np.maximum(strike - S_final[i], 0)
        
        return payoffs
    
    def payoff_binary_put(self, S_final: np.ndarray, strike: float, 
                         payout: float = BINARY_PAYOUT) -> np.ndarray:
        """Binary put: payout if below strike, 0 otherwise"""
        return np.where(S_final < strike, payout, 0)
    
    def payoff_knockout_put(self, paths: np.ndarray, strike: float, 
                           barrier: float) -> np.ndarray:
        """Knockout put: worthless if barrier ever breached, else standard put"""
        payoffs = np.zeros(self.num_simulations)
        S_final = paths[:, -1]
        
        for i in range(self.num_simulations):
            # Check if barrier was breached at any point
            if np.any(paths[i, :] < barrier):
                payoffs[i] = 0  # Knocked out
            else:
                payoffs[i] = np.maximum(strike - S_final[i], 0)
        
        return payoffs
    
    def calculate_pnl(self) -> np.ndarray:
        """
        Calculate portfolio PnL across all simulations
        Returns: (num_simulations,) array of PnL values
        """
        # Find max expiry to generate paths
        max_expiry = max(p.expiry_weeks for p in self.positions 
                        if p.expiry_weeks is not None)
        
        paths = self.generate_price_paths(max_expiry)
        pnl = np.zeros(self.num_simulations)
        
        # Process each position
        for position in self.positions:
            if position.option_type == 'underlying':
                # Underlying: long or short
                S_final = paths[:, -1]
                position_pnl = (S_final - S0) * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            elif position.option_type == 'call':
                # European call at expiry
                steps_to_expiry = weeks_to_steps(position.expiry_weeks)
                S_final = paths[:, steps_to_expiry]
                payoff = self.payoff_call(S_final, position.strike)
                # PnL = payoff - entry_cost
                position_pnl = payoff * position.quantity - position.entry_price * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            elif position.option_type == 'put':
                # European put at expiry
                steps_to_expiry = weeks_to_steps(position.expiry_weeks)
                S_final = paths[:, steps_to_expiry]
                payoff = self.payoff_put(S_final, position.strike)
                position_pnl = payoff * position.quantity - position.entry_price * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            elif position.option_type == 'chooser':
                # Chooser option
                payoff = self.payoff_chooser(paths, position.strike, position.decision_weeks)
                position_pnl = payoff * position.quantity - position.entry_price * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            elif position.option_type == 'binary_put':
                # Binary put
                steps_to_expiry = weeks_to_steps(position.expiry_weeks)
                S_final = paths[:, steps_to_expiry]
                payoff = self.payoff_binary_put(S_final, position.strike)
                position_pnl = payoff * position.quantity - position.entry_price * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            elif position.option_type == 'knockout':
                # Knockout put
                steps_to_expiry = weeks_to_steps(position.expiry_weeks)
                path_subset = paths[:, :steps_to_expiry+1]
                payoff = self.payoff_knockout_put(path_subset, position.strike, position.barrier)
                position_pnl = payoff * position.quantity - position.entry_price * position.quantity
                if position.is_short:
                    position_pnl = -position_pnl
            
            else:
                raise ValueError(f"Unknown option type: {position.option_type}")
            
            pnl += position_pnl
        
        # Apply contract size multiplier
        pnl *= CONTRACT_SIZE
        
        self.pnl_results = pnl
        return pnl

def print_portfolio_summary(positions: List[Position]):
    """Print summary of portfolio positions"""
    print("\n" + "="*80)
    print("PORTFOLIO POSITIONS")
    print("="*80)
    
    total_entry_cost = 0
    for pos in positions:
        direction = "SHORT" if pos.is_short else "LONG"
        entry_cost = pos.entry_price * pos.quantity
        total_entry_cost += entry_cost if not pos.is_short else -entry_cost
        
        print(f"{pos.product:12s} | {direction:5s} {pos.quantity:6.0f} contracts @ {pos.entry_price:7.3f} | "
              f"Cost: {entry_cost:9.0f} | Type: {pos.option_type:12s}")
    
    print("-"*80)
    print(f"Total Portfolio Entry Cost: {total_entry_cost:,.0f}")
    print("="*80)

def print_statistics(pnl: np.ndarray, positions: List[Position]):
    """Print detailed statistics of PnL distribution"""
    print("\n" + "="*80)
    print("MONTE CARLO SIMULATION RESULTS ({} simulations)".format(len(pnl)))
    print("="*80)
    
    # Basic statistics
    mean_pnl = np.mean(pnl)
    std_pnl = np.std(pnl)
    min_pnl = np.min(pnl)
    max_pnl = np.max(pnl)
    median_pnl = np.median(pnl)
    
    print(f"\n📊 PROFIT & LOSS STATISTICS:")
    print(f"  Mean PnL:           {mean_pnl:>12,.0f}")
    print(f"  Median PnL:         {median_pnl:>12,.0f}")
    print(f"  Std Dev:            {std_pnl:>12,.0f}")
    print(f"  Min PnL:            {min_pnl:>12,.0f}")
    print(f"  Max PnL:            {max_pnl:>12,.0f}")
    print(f"  Range:              {max_pnl - min_pnl:>12,.0f}")
    
    # Risk metrics
    prob_profit = np.sum(pnl > 0) / len(pnl) * 100
    prob_loss = np.sum(pnl < 0) / len(pnl) * 100
    breakeven_prob = np.sum(np.abs(pnl) <= 1) / len(pnl) * 100
    
    print(f"\n📈 PROBABILITY METRICS:")
    print(f"  Probability of Profit:     {prob_profit:>6.1f}%")
    print(f"  Probability of Loss:       {prob_loss:>6.1f}%")
    print(f"  Probability of Breakeven:  {breakeven_prob:>6.1f}%")
    
    # VaR and CVaR
    var_95 = np.percentile(pnl, 5)
    var_99 = np.percentile(pnl, 1)
    cvar_95 = np.mean(pnl[pnl <= var_95])
    cvar_99 = np.mean(pnl[pnl <= var_99])
    
    print(f"\n⚠️  RISK METRICS:")
    print(f"  Value at Risk (95%):       {var_95:>12,.0f}")
    print(f"  Value at Risk (99%):       {var_99:>12,.0f}")
    print(f"  Conditional VaR (95%):     {cvar_95:>12,.0f}")
    print(f"  Conditional VaR (99%):     {cvar_99:>12,.0f}")
    
    # Return metrics
    if mean_pnl != 0 and std_pnl != 0:
        sharpe = mean_pnl / std_pnl
        sortino_target = 0
        downside = np.std(pnl[pnl < sortino_target]) if np.any(pnl < sortino_target) else std_pnl
        sortino = mean_pnl / downside if downside > 0 else 0
        
        print(f"\n💹 RETURN METRICS:")
        print(f"  Sharpe Ratio:              {sharpe:>12.3f}")
        print(f"  Sortino Ratio:             {sortino:>12.3f}")
        print(f"  Skewness:                  {skew(pnl):>12.3f}")
        print(f"  Kurtosis:                  {kurtosis(pnl):>12.3f}")
    
    # Percentiles
    print(f"\n📊 PERCENTILES:")
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        val = np.percentile(pnl, p)
        print(f"  {p:>2d}th percentile:         {val:>12,.0f}")
    
    print("="*80)

def create_visualizations(pnl: np.ndarray, positions: List[Position]):
    """Create comprehensive visualization of results"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Distribution of PnL
    ax1 = axes[0, 0]
    ax1.hist(pnl, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
    ax1.axvline(np.mean(pnl), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(pnl):,.0f}')
    ax1.axvline(np.median(pnl), color='green', linestyle='--', linewidth=2, label=f'Median: {np.median(pnl):,.0f}')
    ax1.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax1.set_xlabel('PnL', fontsize=11)
    ax1.set_ylabel('Frequency', fontsize=11)
    ax1.set_title('Distribution of Portfolio PnL', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    # 2. Q-Q plot
    ax2 = axes[0, 1]
    sorted_pnl = np.sort(pnl)
    theoretical = np.sort(np.random.normal(np.mean(pnl), np.std(pnl), len(pnl)))
    ax2.scatter(theoretical, sorted_pnl, alpha=0.6, s=20)
    ax2.plot([theoretical.min(), theoretical.max()], 
             [sorted_pnl.min(), sorted_pnl.max()], 'r--', lw=2)
    ax2.set_xlabel('Theoretical Quantiles', fontsize=11)
    ax2.set_ylabel('Empirical Quantiles', fontsize=11)
    ax2.set_title('Q-Q Plot', fontsize=12, fontweight='bold')
    ax2.grid(alpha=0.3)
    
    # 3. Cumulative probability
    ax3 = axes[1, 0]
    sorted_returns = np.sort(pnl)
    cumulative = np.arange(1, len(sorted_returns) + 1) / len(sorted_returns)
    ax3.plot(sorted_returns, cumulative, linewidth=2, color='steelblue')
    ax3.axhline(0.5, color='red', linestyle='--', alpha=0.5, label='50th percentile')
    ax3.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax3.axhline(0.95, color='orange', linestyle='--', alpha=0.5, label='95th percentile')
    ax3.set_xlabel('PnL', fontsize=11)
    ax3.set_ylabel('Cumulative Probability', fontsize=11)
    ax3.set_title('Cumulative Distribution Function', fontsize=12, fontweight='bold')
    ax3.legend()
    ax3.grid(alpha=0.3)
    
    # 4. Risk-Return scatter with key metrics
    ax4 = axes[1, 1]
    
    # Create boxes for key statistics
    stats_text = f"""
    SIMULATION SUMMARY
    ════════════════════════════════
    Mean PnL:        {np.mean(pnl):>12,.0f}
    Std Dev:         {np.std(pnl):>12,.0f}
    Median PnL:      {np.median(pnl):>12,.0f}
    
    Min PnL:         {np.min(pnl):>12,.0f}
    Max PnL:         {np.max(pnl):>12,.0f}
    
    Prob(Profit):    {np.sum(pnl > 0) / len(pnl) * 100:>11.1f}%
    Prob(Loss):      {np.sum(pnl < 0) / len(pnl) * 100:>11.1f}%
    
    VaR (95%):       {np.percentile(pnl, 5):>12,.0f}
    VaR (99%):       {np.percentile(pnl, 1):>12,.0f}
    ════════════════════════════════
    """
    
    ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes, 
            fontsize=10, verticalalignment='center',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax4.axis('off')
    
    plt.tight_layout()
    plt.savefig('/mnt/user-data/outputs/portfolio_simulation_results.png', dpi=300, bbox_inches='tight')
    print("\n✅ Visualization saved to: portfolio_simulation_results.png")
    
    return fig

# ======================= MAIN =======================
def main():
    """Run the portfolio simulation"""
    
    # Define the optimal portfolio based on the pricer recommendations
    positions = [
        # STRONG BUYS (best edges)
        Position(
            product="AC_45_KO",
            entry_price=0.175,  # Ask price (buying)
            quantity=50,
            option_type="knockout",
            strike=45,
            expiry_weeks=3,
            barrier=35,
            is_short=False
        ),
        
        Position(
            product="AC_40_BP",
            entry_price=5.100,  # Ask price (buying)
            quantity=30,
            option_type="binary_put",
            strike=40,
            expiry_weeks=3,
            is_short=False
        ),
        
        # 2-week options with decent edge
        Position(
            product="AC_50_P_2",
            entry_price=9.750,  # Ask price (buying)
            quantity=20,
            option_type="put",
            strike=50,
            expiry_weeks=2,
            is_short=False
        ),
        
        Position(
            product="AC_50_C_2",
            entry_price=9.750,  # Ask price (buying)
            quantity=20,
            option_type="call",
            strike=50,
            expiry_weeks=2,
            is_short=False
        ),
        
        # STRONG SELL (chooser overpriced)
        Position(
            product="AC_50_CO",
            entry_price=22.200,  # Bid price (selling)
            quantity=15,
            option_type="chooser",
            strike=50,
            expiry_weeks=3,
            decision_weeks=2,
            is_short=True
        ),
        
        # Additional sells to balance risk
        Position(
            product="AC_60_C",
            entry_price=8.800,  # Bid price (selling)
            quantity=15,
            option_type="call",
            strike=60,
            expiry_weeks=3,
            is_short=True
        ),
        
        # Buy some ATM for directional hedge
        Position(
            product="AC_45_P",
            entry_price=9.100,  # Ask price (buying)
            quantity=10,
            option_type="put",
            strike=45,
            expiry_weeks=3,
            is_short=False
        ),
    ]
    
    # Print portfolio
    print_portfolio_summary(positions)
    
    # Run simulation
    simulator = PortfolioSimulator(positions, num_simulations=NUM_SIMULATIONS)
    pnl = simulator.calculate_pnl()
    
    # Print statistics
    print_statistics(pnl, positions)
    
    # Create visualizations
    create_visualizations(pnl, positions)
    
    # Save detailed results to CSV
    results_df = pd.DataFrame({
        'simulation': np.arange(len(pnl)),
        'pnl': pnl,
        'pnl_per_contract': pnl / CONTRACT_SIZE
    })
    results_df.to_csv('/mnt/user-data/outputs/simulation_results.csv', index=False)
    print("✅ Detailed results saved to: simulation_results.csv")
    
    return pnl, simulator

if __name__ == "__main__":
    pnl, simulator = main()