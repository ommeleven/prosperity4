"""
XIREN Round 2 - 150k+ Target Algorithm

Data-calibrated strategy from full analysis of Round 2 historical data.

CORE INSIGHT:
- IPR rises exactly 1000/day (100/per 100k ticks). Holding 80 units from early
  day -1 through day 1 end earns ~2800+ per unit = ~224k+ from trend alone.
- Strategy: get to +80 IPR FAST and stay there. Sell only when market bids are
  extremely high.
- ASH: tight mean-reversion market making around 10000.

EXPECTED PnL:
- IPR (trend + spread): ~235-240k
- ASH (market making): ~13-56k (depending on fill model)
- Total: ~250-292k without MAF
- With MAF +25% volume: ~310-365k

TARGET: 150k is easily achievable with this strategy (even at 60% efficiency).
"""

from datamodel import Order, OrderDepth, TradingState, Symbol
from typing import Dict, List
import json


class Trader:

    POSITION_LIMITS = {
        'ASH_COATED_OSMIUM': 80,
        'INTARIAN_PEPPER_ROOT': 80,
    }

    # ── ASH: mean-reversion around 10000 ─────────────────────────────────────
    ASH_FAIR        = 10000
    ASH_BID_EDGE    = 2     # bid at 9998 (inside market spread of ±8)
    ASH_ASK_EDGE    = 4     # ask at 10004
    ASH_TAKE_THRESH = 4     # aggressively sweep all asks < 9996, bids > 10004
    ASH_MM_QTY      = 20

    # ── IPR: linear trend ─────────────────────────────────────────────────────
    # fair = 11000 + 1000*(day+1) + timestamp*0.001
    # Strategy: stay max LONG (+80) to capture the upward trend.
    # Buy at any ask <= fair+7 (within market spread).
    # Only sell at bids >= fair+8 (taking profit at extreme highs).
    IPR_BUY_MAX_ABOVE_FAIR = 7    # lift asks up to fair+7
    IPR_SELL_MIN_ABOVE_FAIR = 8   # only sell at bids >= fair+8

    # ── MAF ──────────────────────────────────────────────────────────────────
    # Incremental profit from +25% volume ≈ 62k (25% of ~250k).
    # MAF under ~62k is profitable. 10k is conservative & likely top 50%.
    MAF = 10000

    def _clamp(self, qty: int, pos: int, symbol: str) -> int:
        limit = self.POSITION_LIMITS[symbol]
        if qty > 0:
            return min(qty, limit - pos)
        return max(qty, -limit - pos)

    def _ipr_fair(self, state: TradingState) -> float | None:
        """
        IPR fair value: 11000 + 1000*(day+1) + timestamp*0.001
        Day inferred from current mid-price (each day starts 1000 higher).
        """
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
        # day = round((mid - 11000) / 1000) - 1
        # day+1 index: 0=day-1, 1=day0, 2=day1
        day_idx = max(0, min(10, round((mid - 11000) / 1000)))
        day = day_idx - 1
        return 11000 + 1000 * (day + 1) + state.timestamp * 0.001

    def _trade_ash(self, state: TradingState) -> List[Order]:
        """
        ASH: tight market making with full order book sweep.
        - Take aggressively when price deviates > ASH_TAKE_THRESH from 10000.
        - Post passive bid/ask inside the spread with inventory skew.
        """
        symbol = 'ASH_COATED_OSMIUM'
        if symbol not in state.order_depths:
            return []

        od = state.order_depths[symbol]
        pos = state.position.get(symbol, 0)
        orders = []
        fair = self.ASH_FAIR
        limit = self.POSITION_LIMITS[symbol]

        # Inventory skew: shift quotes toward reducing position
        inv_skew = round(-pos / limit * 2)
        our_bid = fair - self.ASH_BID_EDGE + inv_skew
        our_ask = fair + self.ASH_ASK_EDGE + inv_skew

        # ── Sweep all ask levels for aggressive buys ─────────────────────────
        for price in sorted(od.sell_orders.keys()):
            if pos >= limit:
                break
            vol = -od.sell_orders[price]
            if price < fair - self.ASH_TAKE_THRESH:
                # Below take threshold: buy aggressively
                q = min(vol, limit - pos)
                if q > 0:
                    orders.append(Order(symbol, price, q))
                    pos += q
            elif price <= our_bid:
                # Inside our passive bid: fill passively
                q = min(vol, limit - pos, self.ASH_MM_QTY)
                if q > 0:
                    orders.append(Order(symbol, int(our_bid), q))
                    pos += q
                break

        # ── Sweep all bid levels for aggressive sells ────────────────────────
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if pos <= -limit:
                break
            vol = od.buy_orders[price]
            if price > fair + self.ASH_TAKE_THRESH:
                # Above take threshold: sell aggressively
                q = min(vol, limit + pos)
                if q > 0:
                    orders.append(Order(symbol, price, -q))
                    pos -= q
            elif price >= our_ask:
                # At or above our passive ask
                q = min(vol, limit + pos, self.ASH_MM_QTY)
                if q > 0:
                    orders.append(Order(symbol, int(our_ask), -q))
                    pos -= q
                break

        # ── Post remaining passive quotes ─────────────────────────────────────
        buy_q = self._clamp(self.ASH_MM_QTY, pos, symbol)
        if buy_q > 0:
            orders.append(Order(symbol, int(our_bid), buy_q))

        sell_q = self._clamp(-self.ASH_MM_QTY, pos, symbol)
        if sell_q < 0:
            orders.append(Order(symbol, int(our_ask), sell_q))

        return orders

    def _trade_ipr(self, state: TradingState) -> List[Order]:
        """
        IPR: TREND-FOLLOWING LONG BIAS.
        Goal: be at +80 (max long) as quickly as possible and stay there.
        Buy at any ask <= fair + IPR_BUY_MAX_ABOVE_FAIR.
        Only sell at very high bids >= fair + IPR_SELL_MIN_ABOVE_FAIR.
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

        buy_threshold = fair + self.IPR_BUY_MAX_ABOVE_FAIR
        sell_threshold = fair + self.IPR_SELL_MIN_ABOVE_FAIR

        # ── Buy: sweep all asks up to buy_threshold ───────────────────────────
        for price in sorted(od.sell_orders.keys()):
            if pos >= limit or price > buy_threshold:
                break
            vol = -od.sell_orders[price]
            q = min(vol, limit - pos)
            if q > 0:
                orders.append(Order(symbol, price, q))
                pos += q

        # ── Sell: only at very high bids ───────────────────────────────────────
        for price in sorted(od.buy_orders.keys(), reverse=True):
            if pos <= 0 or price < sell_threshold:
                break
            vol = od.buy_orders[price]
            q = min(vol, pos)
            if q > 0:
                orders.append(Order(symbol, price, -q))
                pos -= q

        # ── Also post a passive bid at fair-3 to pick up any cheap sellers ────
        # This is a secondary way to build position at favorable prices
        if pos < limit:
            passive_bid = int(fair - 3)
            q = self._clamp(20, pos, symbol)
            if q > 0:
                orders.append(Order(symbol, passive_bid, q))

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