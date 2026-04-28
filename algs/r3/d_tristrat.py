from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Tuple, Optional
import json
import collections

class Trader:
    def __init__(self):
        # ----- CORRECT POSITION LIMITS (Round 3) -----
        self.position_limits = {
            'HYDROGEL_PACK': 200,
            'VELVETFRUIT_EXTRACT': 200,
            # All 10 VEV options (each limit = 300)
            'VEV_4000': 300,
            'VEV_4500': 300,
            'VEV_5000': 300,
            'VEV_5100': 300,
            'VEV_5200': 300,
            'VEV_5300': 300,
            'VEV_5400': 300,
            'VEV_5500': 300,
            'VEV_6000': 300,
            'VEV_6500': 300,
        }
        # Base order size for each product (adjusted later by inventory & spread)
        self.base_qty = {
            'HYDROGEL_PACK': 10,
            'VELVETFRUIT_EXTRACT': 10,
            'VEV_4000': 20,
            'VEV_4500': 20,
            'VEV_5000': 20,
            'VEV_5100': 20,
            'VEV_5200': 20,
            'VEV_5300': 20,
            'VEV_5400': 20,
            'VEV_5500': 20,
            'VEV_6000': 30,   # wide spread → larger size
            'VEV_6500': 30,
        }
        # For storing rolling mid prices (used in traderData)
        self.window_size = 20

    def get_position_capacity(self, pos: int, is_buy: bool, limit: int) -> int:
        """Remaining contracts we can trade before hitting the limit."""
        if is_buy:
            return max(0, limit - pos)
        else:
            return max(0, limit + pos)

    def compute_fair_value(self, product: str, order_depth: OrderDepth, 
                           mid_history: List[float]) -> Optional[float]:
        """
        Simple fair value for non‑OTM options:
        - For VEV_6000 / VEV_6500, fair value is 0.5 (mid of 0/1).
        - For others, use the mid price of the current book.
        - If history exists, blend with moving average to smooth.
        """
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        current_mid = (best_bid + best_ask) / 2.0

        # Deep OTM options: known artificial spread 0/1
        if product in ('VEV_6000', 'VEV_6500'):
            return 0.5

        # Blend with historical mid if available (mean reversion)
        if mid_history:
            hist_avg = sum(mid_history) / len(mid_history)
            # 70% current mid, 30% historical average -> dampen noise
            return 0.7 * current_mid + 0.3 * hist_avg
        return current_mid

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result = {}

        # ----- Load persistent data (rolling mid prices) -----
        trader_data = state.traderData
        if trader_data:
            data = json.loads(trader_data)
            mid_prices = {k: collections.deque(v, maxlen=self.window_size) 
                          for k, v in data.items()}
        else:
            mid_prices = {}

        # ----- Process each product -----
        for product, order_depth in state.order_depths.items():
            # Skip if we don't have a two‑sided book
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            if best_bid >= best_ask:
                continue

            # Update rolling mid history for this product
            current_mid = (best_bid + best_ask) / 2.0
            if product not in mid_prices:
                mid_prices[product] = collections.deque(maxlen=self.window_size)
            mid_prices[product].append(current_mid)
            mid_history = list(mid_prices[product])

            # Determine fair value (with mean reversion blend)
            fair = self.compute_fair_value(product, order_depth, mid_history)
            if fair is None:
                continue

            # Inventory & limits
            pos = state.position.get(product, 0)
            limit = self.position_limits.get(product, 200)
            base = self.base_qty.get(product, 10)

            # ----- Inventory skew: adjust quantity and price aggressiveness -----
            # If we are long, we want to sell more / buy less; if short, opposite.
            buy_qty = base
            sell_qty = base

            # Aggressive price offsets only when inventory is extreme
            bid_offset = 0
            ask_offset = 0

            if pos > 0:
                # Long: reduce buy size, increase sell size
                buy_qty = max(1, base // 2)
                sell_qty = min(base * 2, base + pos // 5)
                # If very long, offer a more competitive ask (lower than best ask)
                if pos > limit // 2:
                    ask_offset = -1   # sell cheaper to reduce inventory faster
            elif pos < 0:
                # Short: reduce sell size, increase buy size
                sell_qty = max(1, base // 2)
                buy_qty = min(base * 2, base + abs(pos) // 5)
                if pos < -limit // 2:
                    bid_offset = 1    # buy higher to cover short

            # Respect position capacity
            buy_capacity = self.get_position_capacity(pos, True, limit)
            sell_capacity = self.get_position_capacity(pos, False, limit)
            buy_qty = min(buy_qty, buy_capacity)
            sell_qty = min(sell_qty, sell_capacity)

            # ----- Special handling for deep OTM options (guaranteed spread) -----
            if product in ('VEV_6000', 'VEV_6500'):
                # Always bid at 0, ask at 1 – never cross
                orders = []
                if buy_qty > 0:
                    orders.append(Order(product, 0, buy_qty))
                if sell_qty > 0:
                    orders.append(Order(product, 1, -sell_qty))
                if orders:
                    result[product] = orders
                continue

            # ----- Normal market making: place orders at best bid/ask with possible offset -----
            bid_price = best_bid + bid_offset
            ask_price = best_ask + ask_offset

            # Ensure we never cross our own spread
            if bid_price >= ask_price:
                # If offset made us cross, revert to neutral
                bid_price = best_bid
                ask_price = best_ask

            orders = []
            if buy_qty > 0:
                orders.append(Order(product, bid_price, buy_qty))
            if sell_qty > 0:
                orders.append(Order(product, ask_price, -sell_qty))

            if orders:
                result[product] = orders

        # ----- Save updated mid prices for next iteration -----
        # Convert deques to lists for JSON serialization
        new_trader_data = {k: list(v) for k, v in mid_prices.items()}
        traderData = json.dumps(new_trader_data)

        # No conversions needed for Round 3
        conversions = 0
        return result, conversions, traderData

    # Required for Round 2 compatibility (ignored in Round 3)
    def bid(self) -> int:
        return 15