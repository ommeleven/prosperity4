"""
XIREN Round 2 - Maximum Edge Algorithm
Sweeps the entire order book for profitable trades, not just best bid/ask.

Improvements:
- Scans ALL levels of the order book, not just best bid/ask
- Takes ALL profitable levels in one timestamp
- IPR: adapts to current day automatically, uses precise formula
- ASH: tighter risk controls, mean-reversion with full book sweep
- Inventory management: forced liquidation when position > 60% of limit
- High MAF for guaranteed +25% volume access
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    ASH_FAIR        = 10000
    ASH_MM_EDGE     = 4
    ASH_TAKE_THRESH = 6     # sweep all asks below fair-6, bids above fair+6
    ASH_MM_QTY      = 20

    IPR_BID_EDGE    = 4
    IPR_ASK_EDGE    = 7
    IPR_TAKE_THRESH = 9
    IPR_MM_QTY      = 20

    # High MAF for guaranteed top-50% access to +25% volume
    MAF = 15000

    def _clamp(self, qty: int, pos: int, symbol: str) -> int:
        limit = self.POSITION_LIMITS[symbol]
        if qty > 0:
            return min(qty, limit - pos)
        return max(qty, -limit - pos)

    def _ipr_fair(self, state: TradingState) -> float:
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
        day_est = max(0, min(10, round((mid - 11000) / 1000)))
        day = day_est - 1
        return 11000 + 1000 * (day + 1) + state.timestamp * 0.001

    def _sweep_and_make_ash(self, state: TradingState) -> List[Order]:
        symbol = 'ASH_COATED_OSMIUM'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        fair = self.ASH_FAIR
        limit = self.POSITION_LIMITS[symbol]

        # ── Sweep entire book for profitable asks (buy cheap) ─────────────────
        for price in sorted(od.sell_orders.keys()):
            if price >= fair - self.ASH_TAKE_THRESH:
                break
            avail = -od.sell_orders[price]  # sell_orders are negative qty
            q = min(avail, limit - pos)
            if q > 0:
                orders.append(Order(symbol, price, q))
                pos += q

        # ── Sweep entire book for profitable bids (sell high) ─────────────────
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if price <= fair + self.ASH_TAKE_THRESH:
                break
            avail = od.buy_orders[price]
            q = min(avail, limit + pos)
            if q > 0:
                orders.append(Order(symbol, price, -q))
                pos -= q

        # ── Forced inventory reduction when over 60% of limit ─────────────────
        if pos > limit * 0.6 and od.buy_orders:
            # Sell down to 60% limit using best available bids
            target_sell = int(pos - limit * 0.5)
            for price in sorted(od.buy_orders.keys(), reverse=True):
                if target_sell <= 0:
                    break
                if price >= fair - 2:  # don't sell at a big loss
                    avail = od.buy_orders[price]
                    q = min(avail, target_sell, limit + pos)
                    if q > 0:
                        orders.append(Order(symbol, price, -q))
                        pos -= q
                        target_sell -= q

        elif pos < -limit * 0.6 and od.sell_orders:
            target_buy = int(-pos - limit * 0.5)
            for price in sorted(od.sell_orders.keys()):
                if target_buy <= 0:
                    break
                if price <= fair + 2:
                    avail = -od.sell_orders[price]
                    q = min(avail, target_buy, limit - pos)
                    if q > 0:
                        orders.append(Order(symbol, price, q))
                        pos += q
                        target_buy -= q

        # ── Passive market-making ─────────────────────────────────────────────
        inv_skew = round(-pos / limit * 2)
        our_bid = fair - self.ASH_MM_EDGE + inv_skew
        our_ask = fair + self.ASH_MM_EDGE + inv_skew

        q = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, int(our_bid), q))

        q = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, int(our_ask), q))

        return orders

    def _sweep_and_make_ipr(self, state: TradingState) -> List[Order]:
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

        # ── Sweep book for extreme mispricings ────────────────────────────────
        for price in sorted(od.sell_orders.keys()):
            if price >= fair - self.IPR_TAKE_THRESH:
                break
            avail = -od.sell_orders[price]
            q = min(avail, limit - pos)
            if q > 0:
                orders.append(Order(symbol, price, q))
                pos += q

        for price in sorted(od.buy_orders.keys(), reverse=True):
            if price <= fair + self.IPR_TAKE_THRESH:
                break
            avail = od.buy_orders[price]
            q = min(avail, limit + pos)
            if q > 0:
                orders.append(Order(symbol, price, -q))
                pos -= q

        # ── Forced inventory reduction ─────────────────────────────────────────
        if pos > limit * 0.6 and od.buy_orders:
            target_sell = int(pos - limit * 0.5)
            for price in sorted(od.buy_orders.keys(), reverse=True):
                if target_sell <= 0:
                    break
                if price >= fair - 3:
                    avail = od.buy_orders[price]
                    q = min(avail, target_sell, limit + pos)
                    if q > 0:
                        orders.append(Order(symbol, price, -q))
                        pos -= q; target_sell -= q

        elif pos < -limit * 0.6 and od.sell_orders:
            target_buy = int(-pos - limit * 0.5)
            for price in sorted(od.sell_orders.keys()):
                if target_buy <= 0:
                    break
                if price <= fair + 3:
                    avail = -od.sell_orders[price]
                    q = min(avail, target_buy, limit - pos)
                    if q > 0:
                        orders.append(Order(symbol, price, q))
                        pos += q; target_buy -= q

        # ── Passive market-making ─────────────────────────────────────────────
        inv_skew = round(-pos / limit * 3)
        our_bid = int(fair - self.IPR_BID_EDGE + inv_skew)
        our_ask = int(fair + self.IPR_ASK_EDGE + inv_skew)

        if our_bid >= our_ask:
            our_bid = int(fair) - 1
            our_ask = int(fair) + 1

        q = self._clamp(self.IPR_MM_QTY, pos, symbol)
        if q > 0:
            orders.append(Order(symbol, our_bid, q))

        q = self._clamp(-self.IPR_MM_QTY, pos, symbol)
        if q < 0:
            orders.append(Order(symbol, our_ask, q))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        conversions = 0

        ash = self._sweep_and_make_ash(state)
        if ash:
            result['ASH_COATED_OSMIUM'] = ash

        ipr = self._sweep_and_make_ipr(state)
        if ipr:
            result['INTARIAN_PEPPER_ROOT'] = ipr

        trader_data = json.dumps({"market_access_fee": self.MAF})
        return result, conversions, trader_data
