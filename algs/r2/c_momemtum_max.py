"""
XIREN Round 2 - Maximum PnL Algorithm (~292k simulated, target 150k+ realistic)

STRATEGY RATIONALE:
IPR (TREND): Positions carry across all 3 days in a round.
  IPR rises ~1000/day. Buying 80 units on day -1 and holding to day 1 end
  gains 80 * ~3000 = ~240k from the trend alone.
  => MAXIMIZE LONG POSITION FROM DAY 1 START. Stay at +80 always.

ASH (MEAN REVERSION): Stationary around 10000 with ~16 tick spread.
  Market makes at ±2-4 ticks. Sweeps entire order book each tick.
  => 25-56k depending on fill efficiency.

KEY DIFFERENCES FROM PREVIOUS ALGOS:
1. IPR: Aggressively lifts ALL asks at or below fair+7 to build position fast
2. IPR: Uses fair+8 as sell threshold (vs old fair+7) for better PnL
3. IPR: Also posts a deep passive bid at fair-5 as backup
4. ASH: Sweeps 3 book levels per tick, not just best bid/ask
5. ASH: Lower take threshold (4 vs 7) captures more mean-reversion
6. High MAF (15000) ensures top-50% volume access
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    # ASH parameters (calibrated to ~56k in trade-based simulation)
    ASH_FAIR = 10000
    ASH_BID_EDGE = 2
    ASH_ASK_EDGE = 4
    ASH_TAKE_THRESH = 4
    ASH_MM_QTY = 20

    # IPR parameters (calibrated to ~236-240k in simulation)
    # fair = 11000 + 1000*(day+1) + timestamp*0.001
    IPR_AGGRO_BUY_THRESHOLD = 7    # lift any ask <= fair+7
    IPR_SELL_THRESHOLD = 8         # only sell at bids >= fair+8
    IPR_PASSIVE_BID_EDGE = 5       # also post bid at fair-5 (backup fill)
    IPR_MM_QTY = 20

    MAF = 15000   # 15k: confident top-50%; incremental value ~62k

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

        # Sweep asks (buy): aggressive takes + passive fills
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
                q = min(vol, limit - pos, self.ASH_MM_QTY)
                if q > 0:
                    orders.append(Order(symbol, int(our_bid), q))
                    pos += q
                break

        # Sweep bids (sell): aggressive takes + passive fills
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
                q = min(vol, limit + pos, self.ASH_MM_QTY)
                if q > 0:
                    orders.append(Order(symbol, int(our_ask), -q))
                    pos -= q
                break

        # Post remaining passive quotes at both levels
        buy_q = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if buy_q > 0:
            orders.append(Order(symbol, int(our_bid), buy_q))

        sell_q = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if sell_q < 0:
            orders.append(Order(symbol, int(our_ask), sell_q))

        # Level 2: deeper passive quotes for additional fills
        bid2 = fair - self.ASH_BID_EDGE - 3 + inv_skew
        ask2 = fair + self.ASH_ASK_EDGE + 3 + inv_skew
        buy_q2 = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if buy_q2 > 0:
            orders.append(Order(symbol, int(bid2), buy_q2))
        sell_q2 = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if sell_q2 < 0:
            orders.append(Order(symbol, int(ask2), sell_q2))

        return orders

    def _trade_ipr(self, state: TradingState) -> List[Order]:
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

        buy_cap = fair + self.IPR_AGGRO_BUY_THRESHOLD
        sell_floor = fair + self.IPR_SELL_THRESHOLD

        # ── Primary: buy ALL available asks up to fair+7 ──────────────────────
        for price in sorted(od.sell_orders.keys()):
            if pos >= limit or price > buy_cap:
                break
            vol = -od.sell_orders[price]
            q = min(vol, limit - pos)
            if q > 0:
                orders.append(Order(symbol, price, q))
                pos += q

        # ── Sell at very high bids ────────────────────────────────────────────
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if pos <= 0 or price < sell_floor:
                break
            vol = od.buy_orders[price]
            q = min(vol, pos)
            if q > 0:
                orders.append(Order(symbol, price, -q))
                pos -= q

        # ── Passive bid for catching cheap sellers ────────────────────────────
        if pos < limit:
            passive_bid = int(fair - self.IPR_PASSIVE_BID_EDGE)
            q = self._clamp(self.IPR_MM_QTY, pos, symbol)
            if q > 0:
                orders.append(Order(symbol, passive_bid, q))

        # ── Also passive ask for the occasions bids spike ─────────────────────
        if pos > 0:
            passive_ask = int(fair + self.IPR_SELL_THRESHOLD)
            q = self._clamp(-self.IPR_MM_QTY, pos, symbol)
            if q < 0:
                orders.append(Order(symbol, passive_ask, q))

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
