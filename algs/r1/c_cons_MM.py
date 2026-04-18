"""
IMPROVED XIREN Trading Algorithm - Round 1
Based on post-mortem of submission 177180 (PnL: ~22,102)

ROOT CAUSE FIXES vs original (177180.py):

1. IPR FAIR VALUE: Old algo used smoothed mid-price -> lagged actual fair by up to 1000 XIRECS.
   Fix: Use the known linear formula: fair = 9998.5 + 1000*(day+2) + timestamp*0.001
   Day is inferred from current mid-price.

2. IPR EDGE: Old edge=1 is INSIDE the market spread of ~13. Only adverse-selection fills.
   Fix: Post bid at fair-4 (better than market's ~fair-5), ask at fair+6 (better than ~fair+8).
   Now we're the best price in the book, attracting real directional flow.

3. ASH EDGE: Old edge=2 with market spread ~16. Functional but thin.
   Fix: Widen to edge=3, with aggressive takes when |price - 10000| > 7.
   More fills at better prices.

4. QUANTITY: Old max_quantity=min(10, limit-abs(pos)) was too small per tick.
   Fix: Post larger sizes (15) to increase fill probability, take up to 30 aggressively.

5. IPR DIRECTION BIAS: IPR trends up 0.1/tick. Slight long bias improves P&L.
   Fix: Asymmetric quoting - bid at fair-3 (more likely to fill), ask at fair+7.

6. STATE: Trader object IS preserved between timestamps in Prosperity, but __init__
   is only called once per session. No bug there - removed unnecessary list tracking.
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:
    
    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }
    
    # ASH: stationary mean-reverting around 10000
    ASH_FAIR = 10000
    ASH_MM_EDGE = 3          # post bid/ask ±3 from fair (inside market spread of ±8)
    ASH_TAKE_THRESH = 7      # aggressively hit market if |price - fair| > 7
    ASH_MM_QTY = 15          # larger passive order size
    ASH_TAKE_QTY = 30        # larger aggressive size

    # IPR: perfectly linear trend
    # fair(day, t) = 9998.5 + 1000*(day+2) + t*0.001
    # Market structure: bids ~fair-5, asks ~fair+8 (spread ~13)
    IPR_BASE = 9998.5
    IPR_DAY_STEP = 1000
    IPR_TICK_SLOPE = 0.001
    IPR_BID_EDGE = 4         # post bid at fair-4 (best bid in book, above market ~fair-5)
    IPR_ASK_EDGE = 6         # post ask at fair+6 (best ask in book, below market ~fair+8)
    IPR_TAKE_THRESH = 9      # aggressively take if market deviates >9 from fair
    IPR_MM_QTY = 15
    IPR_TAKE_QTY = 30

    def _clamp(self, qty: int, pos: int, product: str) -> int:
        """Clamp quantity so position stays within limits."""
        limit = self.POSITION_LIMITS[product]
        if qty > 0:
            return min(qty, limit - pos)
        else:
            return max(qty, -limit - pos)

    def _best_bid(self, od: OrderDepth):
        if od.buy_orders:
            p = max(od.buy_orders)
            return p, od.buy_orders[p]
        return None, None

    def _best_ask(self, od: OrderDepth):
        if od.sell_orders:
            p = min(od.sell_orders)
            return p, od.sell_orders[p]
        return None, None

    def _ipr_fair(self, state: TradingState) -> float:
        """
        Compute IPR fair value from the known linear formula.
        Day is inferred from current mid-price.
        fair = 9998.5 + 1000*(day+2) + timestamp*0.001
        """
        od = state.order_depths.get('INTARIAN_PEPPER_ROOT')
        if od is None:
            return None
        
        bb, _ = self._best_bid(od)
        ba, _ = self._best_ask(od)
        
        if bb and ba:
            mid = (bb + ba) / 2
        elif bb:
            mid = bb + 8   # market asks ~8 above fair
        elif ba:
            mid = ba - 8
        else:
            return None
        
        # Infer day: fair ≈ IPR_BASE + 1000*(day+2)  (ignoring small timestamp term)
        day_est = round((mid - self.IPR_BASE) / self.IPR_DAY_STEP) - 2
        day_est = max(-2, min(5, day_est))
        
        fair = self.IPR_BASE + self.IPR_DAY_STEP * (day_est + 2) + state.timestamp * self.IPR_TICK_SLOPE
        return round(fair, 1)

    def _trade_ash(self, state: TradingState) -> List[Order]:
        symbol = 'ASH_COATED_OSMIUM'
        if symbol not in state.order_depths:
            return []
        
        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        
        fair = self.ASH_FAIR
        bb_price, _ = self._best_bid(od)
        ba_price, _ = self._best_ask(od)
        
        # ── Aggressive takes ──────────────────────────────────────────────────
        if ba_price is not None and ba_price < fair - self.ASH_TAKE_THRESH:
            qty = self._clamp(self.ASH_TAKE_QTY, pos, symbol)
            if qty > 0:
                orders.append(Order(symbol, ba_price, qty))
                pos += qty

        if bb_price is not None and bb_price > fair + self.ASH_TAKE_THRESH:
            qty = self._clamp(-self.ASH_TAKE_QTY, pos, symbol)
            if qty < 0:
                orders.append(Order(symbol, bb_price, qty))
                pos += qty

        # ── Passive market-making with inventory skew ─────────────────────────
        # Skew quotes toward reducing inventory: if long, lower bid/raise ask
        inv_ratio = pos / self.POSITION_LIMITS[symbol]   # -1 to +1
        skew = round(inv_ratio * 2)  # ±2 ticks skew at position limit

        our_bid = fair - self.ASH_MM_EDGE - skew
        our_ask = fair + self.ASH_MM_EDGE - skew  # note: -skew here too (skew bids and asks same direction)

        buy_qty = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if buy_qty > 0:
            orders.append(Order(symbol, int(our_bid), buy_qty))

        sell_qty = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if sell_qty < 0:
            orders.append(Order(symbol, int(our_ask), sell_qty))

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
        
        bb_price, _ = self._best_bid(od)
        ba_price, _ = self._best_ask(od)

        # ── Aggressive takes ──────────────────────────────────────────────────
        if ba_price is not None and ba_price < fair - self.IPR_TAKE_THRESH:
            qty = self._clamp(self.IPR_TAKE_QTY, pos, symbol)
            if qty > 0:
                orders.append(Order(symbol, ba_price, qty))
                pos += qty

        if bb_price is not None and bb_price > fair + self.IPR_TAKE_THRESH:
            qty = self._clamp(-self.IPR_TAKE_QTY, pos, symbol)
            if qty < 0:
                orders.append(Order(symbol, bb_price, qty))
                pos += qty

        # ── Passive market-making ─────────────────────────────────────────────
        # Inventory skew: if long, push quotes down; if short, push up
        inv_ratio = pos / self.POSITION_LIMITS[symbol]
        skew = round(inv_ratio * 3)  # up to ±3 ticks at limit

        our_bid = int(fair - self.IPR_BID_EDGE - skew)
        our_ask = int(fair + self.IPR_ASK_EDGE - skew)

        # Safety: don't cross our own spread
        if our_bid >= our_ask:
            our_bid = int(fair) - 1
            our_ask = int(fair) + 1

        buy_qty = self._clamp(self.IPR_MM_QTY, pos, symbol)
        if buy_qty > 0:
            orders.append(Order(symbol, our_bid, buy_qty))

        sell_qty = self._clamp(-self.IPR_MM_QTY, pos, symbol)
        if sell_qty < 0:
            orders.append(Order(symbol, our_ask, sell_qty))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        conversions = 0
        trader_data = ""

        ash_orders = self._trade_ash(state)
        if ash_orders:
            result['ASH_COATED_OSMIUM'] = ash_orders

        ipr_orders = self._trade_ipr(state)
        if ipr_orders:
            result['INTARIAN_PEPPER_ROOT'] = ipr_orders

        return result, conversions, trader_data
