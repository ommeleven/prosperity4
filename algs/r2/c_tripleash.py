"""
XIREN Round 2 - Ultra Aggressive (Maximum Volume + Trend Exploitation)

This algorithm pushes every parameter to the maximum:
- IPR: Buys at MARKET (hits best ask immediately every tick if not at limit)
- ASH: Sweeps entire book, dual-level posting, very tight spread capture
- MAF: High (20k) to guarantee top-50% access for +25% volume
- Position management: almost zero inventory delay

When to use this vs primary:
- Use this if you're confident on leaderboard and want to maximize.
- Use primary if you want safer, more predictable behavior.

Simulation: ~255k base, ~319k with MAF. Conservative real-world: ~150-200k.
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    ASH_FAIR = 10000
    ASH_BID_EDGE = 2
    ASH_ASK_EDGE = 4
    ASH_TAKE_THRESH = 4
    ASH_MM_QTY = 25

    # IPR: buy everything up to fair+7, sell only at fair+8+
    IPR_BUY_UP_TO = 7
    IPR_SELL_FROM = 8
    IPR_MM_QTY = 25

    MAF = 20000

    def _clamp(self, qty: int, pos: int, symbol: str) -> int:
        limit = self.POSITION_LIMITS[symbol]
        if qty > 0:
            return min(qty, limit - pos)
        return max(qty, -limit - pos)

    def _ipr_fair(self, state: TradingState) -> float | None:
        od = state.order_depths.get('INTARIAN_PEPPER_ROOT')
        if od is None:
            return None
        bb = max(od.buy_orders) if od.buy_orders else None
        ba = min(od.sell_orders) if od.sell_orders else None
        if bb and ba:
            mid = (bb + ba) / 2
        elif bb:
            mid = bb + 7
        elif ba:
            mid = ba - 7
        else:
            return None
        day_idx = max(0, min(10, round((mid - 11000) / 1000)))
        day = day_idx - 1
        return 11000 + 1000 * (day + 1) + state.timestamp * 0.001

    def _trade_ash(self, state: TradingState) -> List[Order]:
        symbol = 'ASH_COATED_OSMIUM'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        fair = self.ASH_FAIR
        limit = self.POSITION_LIMITS[symbol]
        inv_skew = round(-pos / limit * 2)
        our_bid = fair - self.ASH_BID_EDGE + inv_skew
        our_ask = fair + self.ASH_ASK_EDGE + inv_skew

        # Full sweep of ask side
        for price in sorted(od.sell_orders.keys()):
            if pos >= limit:
                break
            vol = -od.sell_orders[price]
            if price < fair - self.ASH_TAKE_THRESH:
                q = min(vol, limit - pos)
                if q > 0:
                    orders.append(Order(symbol, price, q))
                    pos += q
            elif price <= our_bid:
                q = min(vol, limit - pos)
                if q > 0:
                    orders.append(Order(symbol, int(our_bid), q))
                    pos += q
                break

        # Full sweep of bid side
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if pos <= -limit:
                break
            vol = od.buy_orders[price]
            if price > fair + self.ASH_TAKE_THRESH:
                q = min(vol, limit + pos)
                if q > 0:
                    orders.append(Order(symbol, price, -q))
                    pos -= q
            elif price >= our_ask:
                q = min(vol, limit + pos)
                if q > 0:
                    orders.append(Order(symbol, int(our_ask), -q))
                    pos -= q
                break

        # Passive quotes at 3 levels
        for edge_add, qty in [(0, self.ASH_MM_QTY), (3, 15), (6, 10)]:
            bid_p = int(our_bid - edge_add)
            ask_p = int(our_ask + edge_add)
            bq = self._clamp(qty, pos, symbol)
            if bq > 0:
                orders.append(Order(symbol, bid_p, bq))
            sq = self._clamp(-qty, pos, symbol)
            if sq < 0:
                orders.append(Order(symbol, ask_p, sq))

        return orders

    def _trade_ipr(self, state: TradingState) -> List[Order]:
        """
        Ultra-aggressive IPR: buy literally all available asks at/below fair+7.
        This ensures we hit max long ASAP.
        """
        symbol = 'INTARIAN_PEPPER_ROOT'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        limit = self.POSITION_LIMITS[symbol]

        fair = self._ipr_fair(state)
        if fair is None:
            return []

        # BUY: sweep all asks up to fair+7
        for price in sorted(od.sell_orders.keys()):
            if pos >= limit or price > fair + self.IPR_BUY_UP_TO:
                break
            vol = -od.sell_orders[price]
            q = min(vol, limit - pos)
            if q > 0:
                orders.append(Order(symbol, price, q))
                pos += q

        # SELL: only at bids >= fair+8
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if price < fair + self.IPR_SELL_FROM:
                break
            vol = od.buy_orders[price]
            q = min(vol, pos)
            if q > 0:
                orders.append(Order(symbol, price, -q))
                pos -= q

        # Passive orders: bid at fair-3 to catch market sells
        # and ask at fair+8 in case of spike
        if pos < limit:
            q = self._clamp(self.IPR_MM_QTY, pos, symbol)
            if q > 0:
                orders.append(Order(symbol, int(fair - 3), q))

        if pos > 0:
            q = self._clamp(-self.IPR_MM_QTY, pos, symbol)
            if q < 0:
                orders.append(Order(symbol, int(fair + self.IPR_SELL_FROM), q))

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
