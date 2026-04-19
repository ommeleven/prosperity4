"""
XIREN Round 2 - Balanced Market Maker
Data-calibrated from 3 days of Round 2 historical data.

Key parameters derived from data:
- ASH: mean-reverts around 10000, spread ~16 (bids fair-7, asks fair+9)
- IPR: linear trend fair = 11000 + 1000*(day+1) + timestamp*0.001
        market bids at fair-7, asks at fair+7

Strategy: tight inside-spread market making + aggressive takes on large deviations.
MAF: 500 (modest - ensure trading access without over-committing)
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    # ── ASH parameters (mean-reversion, fair=10000) ──────────────────────────
    ASH_FAIR        = 10000
    ASH_MM_EDGE     = 4     # post bid/ask ±4 (market spread ±8); best price in book
    ASH_TAKE_THRESH = 7     # take aggressively if |market_price - 10000| > 7
    ASH_MM_QTY      = 15
    ASH_TAKE_QTY    = 30

    # ── IPR parameters (linear trend) ────────────────────────────────────────
    # fair = 11000 + 1000*(day+1) + timestamp*0.001
    # market: bids fair-7, asks fair+7
    IPR_BID_EDGE    = 4     # bid at fair-4 (inside market bid of fair-7)
    IPR_ASK_EDGE    = 7     # ask at fair+7 (matches market ask -- compete at best ask)
    IPR_TAKE_THRESH = 9     # take if market deviates > 9 from fair
    IPR_MM_QTY      = 15
    IPR_TAKE_QTY    = 30

    # ── Market Access Fee ─────────────────────────────────────────────────────
    # Set to a value you're confident puts you in the top 50% of competitors.
    # Incremental profit from +25% volume is ~21k, so MAF up to ~21k is profitable.
    MAF = 500  # conservative — adjust upward based on leaderboard intel

    def _clamp(self, qty: int, pos: int, symbol: str) -> int:
        limit = self.POSITION_LIMITS[symbol]
        if qty > 0:
            return min(qty, limit - pos)
        return max(qty, -limit - pos)

    def _best_bid(self, od):
        if od.buy_orders:
            p = max(od.buy_orders)
            return p, od.buy_orders[p]
        return None, None

    def _best_ask(self, od):
        if od.sell_orders:
            p = min(od.sell_orders)
            return p, od.sell_orders[p]
        return None, None

    def _ipr_fair(self, state: TradingState) -> float:
        """
        Exact fair value from historical calibration:
        fair = 11000 + 1000*(day+1) + timestamp*0.001
        Day is inferred from current mid-price.
        """
        od = state.order_depths.get('INTARIAN_PEPPER_ROOT')
        if od is None:
            return None

        bb, _ = self._best_bid(od)
        ba, _ = self._best_ask(od)

        if bb and ba:
            mid = (bb + ba) / 2
        elif bb:
            mid = bb + 7
        elif ba:
            mid = ba - 7
        else:
            return None

        # Infer which day we're on (each day starts 1000 higher)
        # day: round((mid - 11000) / 1000) - 1 but clamped
        day_est = round((mid - 11000) / 1000)  # gives 0 for day-1, 1 for day0, 2 for day1
        day_est = max(0, min(10, day_est))
        # Convert: day_est = day + 1, so day = day_est - 1
        day = day_est - 1

        return 11000 + 1000 * (day + 1) + state.timestamp * 0.001

    def _trade_ash(self, state: TradingState) -> List[Order]:
        symbol = 'ASH_COATED_OSMIUM'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        fair = self.ASH_FAIR

        bb, _ = self._best_bid(od)
        ba, _ = self._best_ask(od)

        # Aggressive takes
        if ba is not None and ba < fair - self.ASH_TAKE_THRESH:
            q = self._clamp(self.ASH_TAKE_QTY, pos, symbol)
            if q > 0:
                orders.append(Order(symbol, ba, q))
                pos += q

        if bb is not None and bb > fair + self.ASH_TAKE_THRESH:
            q = self._clamp(-self.ASH_TAKE_QTY, pos, symbol)
            if q < 0:
                orders.append(Order(symbol, bb, q))
                pos += q

        # Passive market-making with inventory skew
        inv_skew = round(-pos / self.POSITION_LIMITS[symbol] * 2)
        our_bid = fair - self.ASH_MM_EDGE + inv_skew
        our_ask = fair + self.ASH_MM_EDGE + inv_skew

        buy_q = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if buy_q > 0:
            orders.append(Order(symbol, int(our_bid), buy_q))

        sell_q = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if sell_q < 0:
            orders.append(Order(symbol, int(our_ask), sell_q))

        return orders

    def _trade_ipr(self, state: TradingState) -> List[Order]:
        symbol = 'INTARIAN_PEPPER_ROOT'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []

        fair = self._ipr_fair(state)
        if fair is None:
            return []

        bb, _ = self._best_bid(od)
        ba, _ = self._best_ask(od)

        # Aggressive takes
        if ba is not None and ba < fair - self.IPR_TAKE_THRESH:
            q = self._clamp(self.IPR_TAKE_QTY, pos, symbol)
            if q > 0:
                orders.append(Order(symbol, ba, q))
                pos += q

        if bb is not None and bb > fair + self.IPR_TAKE_THRESH:
            q = self._clamp(-self.IPR_TAKE_QTY, pos, symbol)
            if q < 0:
                orders.append(Order(symbol, bb, q))
                pos += q

        # Passive market-making
        inv_skew = round(-pos / self.POSITION_LIMITS[symbol] * 3)
        our_bid = int(fair - self.IPR_BID_EDGE + inv_skew)
        our_ask = int(fair + self.IPR_ASK_EDGE + inv_skew)

        if our_bid >= our_ask:
            our_bid = int(fair) - 1
            our_ask = int(fair) + 1

        buy_q = self._clamp(self.IPR_MM_QTY, pos, symbol)
        if buy_q > 0:
            orders.append(Order(symbol, our_bid, buy_q))

        sell_q = self._clamp(-self.IPR_MM_QTY, pos, symbol)
        if sell_q < 0:
            orders.append(Order(symbol, our_ask, sell_q))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        conversions = 0

        ash_orders = self._trade_ash(state)
        if ash_orders:
            result['ASH_COATED_OSMIUM'] = ash_orders

        ipr_orders = self._trade_ipr(state)
        if ipr_orders:
            result['INTARIAN_PEPPER_ROOT'] = ipr_orders

        # Market Access Fee: embed in trader_data as JSON
        # The platform reads this to determine MAF submission.
        trader_data = json.dumps({"market_access_fee": self.MAF})

        return result, conversions, trader_data
