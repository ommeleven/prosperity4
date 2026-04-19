"""
Minimal but extensible backtesting engine for IMC Prosperity-style datasets.
Supports:
- Price + trade ingestion (multiple days)
- Feature computation hooks
- Strategy interface
- Event-driven simulation
- PnL tracking

Assumptions:
- Top-of-book data (bid/ask level 1)
- Simple fill model (market/limit approximation)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List
import glob

# =========================
# Data Loader
# =========================

def load_data(price_pattern: str, trade_pattern: str = None):
    price_files = sorted(glob.glob(price_pattern))
    prices = pd.concat([pd.read_csv(f) for f in price_files])

    trades = None
    if trade_pattern:
        trade_files = sorted(glob.glob(trade_pattern))
        trades = pd.concat([pd.read_csv(f) for f in trade_files])

    return prices, trades


# =========================
# Feature Engine
# =========================

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["mid"] = (df["bid_price_1"] + df["ask_price_1"]) / 2

    df["imbalance"] = (
        (df["bid_volume_1"] - df["ask_volume_1"]) /
        (df["bid_volume_1"] + df["ask_volume_1"] + 1e-9)
    )

    df["microprice"] = (
        df["bid_price_1"] * df["ask_volume_1"] +
        df["ask_price_1"] * df["bid_volume_1"]
    ) / (df["bid_volume_1"] + df["ask_volume_1"] + 1e-9)

    df["return"] = df["mid"].pct_change()

    return df


# =========================
# Strategy Interface
# =========================

class Strategy:
    def on_data(self, row: pd.Series, state: dict) -> Dict[str, int]:
        """
        Return: {"BUY": qty, "SELL": qty}
        """
        raise NotImplementedError


# Example Strategy
class ImbalanceStrategy(Strategy):
    def on_data(self, row, state):
        pos = state.get("position", 0)
        signal = row["imbalance"]

        if signal > 0.5 and pos <= 0:
            return {"BUY": 1}
        elif signal < -0.5 and pos >= 0:
            return {"SELL": 1}
        return {}


# =========================
# Portfolio / Execution
# =========================

@dataclass
class Portfolio:
    cash: float = 0.0
    position: int = 0
    avg_price: float = 0.0

    def update(self, price: float):
        return self.cash + self.position * price


class Backtester:
    def __init__(self, df: pd.DataFrame, strategy: Strategy):
        self.df = df.sort_values("timestamp")
        self.strategy = strategy
        self.portfolio = Portfolio()
        self.history = []

    def execute_order(self, row, action):
        price = row["ask_price_1"] if action == "BUY" else row["bid_price_1"]

        if action == "BUY":
            self.portfolio.cash -= price
            self.portfolio.position += 1

        elif action == "SELL":
            self.portfolio.cash += price
            self.portfolio.position -= 1

    def run(self):
        state = {"position": 0}

        for _, row in self.df.iterrows():

            signal = self.strategy.on_data(row, state)

            for action, qty in signal.items():
                for _ in range(qty):
                    self.execute_order(row, action)

            state["position"] = self.portfolio.position

            pnl = self.portfolio.update(row["mid"])

            self.history.append({
                "timestamp": row["timestamp"],
                "mid": row["mid"],
                "position": self.portfolio.position,
                "pnl": pnl
            })

        return pd.DataFrame(self.history)


# =========================
# Metrics
# =========================

def compute_metrics(results: pd.DataFrame):
    results["returns"] = results["pnl"].pct_change()

    sharpe = np.nan
    if results["returns"].std() > 0:
        sharpe = results["returns"].mean() / results["returns"].std() * np.sqrt(252)

    return {
        "final_pnl": results["pnl"].iloc[-1],
        "sharpe": sharpe,
        "max_position": results["position"].abs().max()
    }


# =========================
# Run Example
# =========================

if __name__ == "__main__":

    prices, trades = load_data("prices_round_2_day_*.csv")

    df = prices[prices["product"] == "CROISSANTS"]
    df = add_features(df)

    strat = ImbalanceStrategy()
    bt = Backtester(df, strat)

    results = bt.run()
    metrics = compute_metrics(results)

    print(metrics)
