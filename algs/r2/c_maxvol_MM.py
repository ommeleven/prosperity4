"""
XIREN Round 2 - Aggressive Market Maker (Maximum Volume)
Optimized for top PnL with high MAF to secure +25% volume access.

Key improvements over balanced:
- Larger order sizes (20 passive, 40 take) for more fills per tick
- Tighter ASH quoting at ±3 to maximise fill rate
- Two-level passive laddering on ASH for depth
- IPR: keep asymmetric quoting (bid fair-4, ask fair+7) which historically optimal
- High MAF (10,000) to very likely secure top 50% contract
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    # ── ASH ──────────────────────────────────────────────────────────────────
    ASH_FAIR        = 10000
    ASH_MM_EDGE     = 4
    ASH_MM_EDGE_2   = 7     # second passive level
    ASH_TAKE_THRESH = 6     # lower threshold = more aggressive takes
    ASH_MM_QTY      = 20
    ASH_MM_QTY_2    = 15
    ASH_TAKE_QTY    = 40

    # ── IPR ──────────────────────────────────────────────────────────────────
    IPR_BID_EDGE    = 4
    IPR_ASK_EDGE    = 7
    IPR_TAKE_THRESH = 9
    IPR_MM_QTY      = 20
    IPR_MM_QTY_2    = 10    # second level
    IPR_TAKE_QTY    = 40

    # ── MAF ──────────────────────────────────────────────────────────────────
    # High MAF ensures top-50% contract. Incremental profit from +25% volume
    # is ~21k on base PnL of ~95k. 10k MAF is profitable if we make top 50%.
    MAF = 10000

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
        day_est = max(0, min(10, round((mid - 11000) / 1000)))
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

        # Level 1: tight passive quotes
        inv_skew = round(-pos / self.POSITION_LIMITS[symbol] * 2)
        bid1 = fair - self.ASH_MM_EDGE + inv_skew
        ask1 = fair + self.ASH_MM_EDGE + inv_skew

        q = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, int(bid1), q))
            pos += q  # track for level 2

        q = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, int(ask1), q))
            pos += q

        # Level 2: wider passive for additional fills
        bid2 = fair - self.ASH_MM_EDGE_2 + inv_skew
        ask2 = fair + self.ASH_MM_EDGE_2 + inv_skew

        q = self._clamp(self.ASH_MM_QTY_2, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, int(bid2), q))
            pos += q

        q = self._clamp(-self.ASH_MM_QTY_2, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, int(ask2), q))

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

        # Level 1 passive
        inv_skew = round(-pos / self.POSITION_LIMITS[symbol] * 3)
        our_bid = int(fair - self.IPR_BID_EDGE + inv_skew)
        our_ask = int(fair + self.IPR_ASK_EDGE + inv_skew)

        if our_bid >= our_ask:
            our_bid = int(fair) - 1
            our_ask = int(fair) + 1

        q = self._clamp(self.IPR_MM_QTY, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, our_bid, q))
            pos += q

        q = self._clamp(-self.IPR_MM_QTY, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, our_ask, q))
            pos += q

        # Level 2 passive (additional depth)
        our_bid_2 = int(fair - self.IPR_BID_EDGE - 3 + inv_skew)
        our_ask_2 = int(fair + self.IPR_ASK_EDGE + 3 + inv_skew)

        q = self._clamp(self.IPR_MM_QTY_2, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, our_bid_2, q))
            pos += q

        q = self._clamp(-self.IPR_MM_QTY_2, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, our_ask_2, q))

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

        trader_data = json.dumps({"market_access_fee": self.MAF})
        return result, conversions, trader_data
