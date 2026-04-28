from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Tuple

class Trader:
    def __init__(self):
        # Position limits as given in Round 3
        self.position_limits = {
            'VELVETFRUIT_EXTRACT': 100,
            'HYDROGEL_PACK': 100,
            'VEV_4000': 1000,
            'VEV_4500': 1000,
            'VEV_5000': 1000,
            'VEV_5100': 1000,
            'VEV_5200': 1000,
            'VEV_5300': 1000,
            'VEV_5400': 1000,
            'VEV_5500': 1000,
            'VEV_6000': 1000,
            'VEV_6500': 1000,
        }
        # Base order size for each product (adjusted by inventory)
        self.base_order_size = {
            'VELVETFRUIT_EXTRACT': 5,
            'HYDROGEL_PACK': 5,
            'VEV_4000': 20,
            'VEV_4500': 20,
            'VEV_5000': 20,
            'VEV_5100': 20,
            'VEV_5200': 20,
            'VEV_5300': 20,
            'VEV_5400': 20,
            'VEV_5500': 20,
            'VEV_6000': 20,
            'VEV_6500': 20,
        }

    def get_position_capacity(self, pos: int, is_buy: bool, limit: int) -> int:
        """Remaining capacity before hitting the position limit."""
        if is_buy:
            return max(0, limit - pos)
        else:
            return max(0, limit + pos)   # selling reduces position (negative pos)

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result = {}

        for product, order_depth in state.order_depths.items():
            # Need both sides of the book
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            # Only trade if there is a positive spread (always true, but guard)
            if best_bid >= best_ask:
                continue

            current_pos = state.position.get(product, 0)
            limit = self.position_limits.get(product, 100)
            base_qty = self.base_order_size.get(product, 10)

            # Inventory skew: reduce quantity on the side that increases inventory
            # when we are already far from zero.
            buy_qty = base_qty
            sell_qty = base_qty

            if current_pos > 0:
                # Long: reduce buys, increase sells
                buy_qty = max(1, base_qty // 2)
                sell_qty = min(base_qty * 2, base_qty + current_pos // 10)
            elif current_pos < 0:
                # Short: reduce sells, increase buys
                sell_qty = max(1, base_qty // 2)
                buy_qty = min(base_qty * 2, base_qty + abs(current_pos) // 10)

            # Respect position limits
            buy_capacity = self.get_position_capacity(current_pos, True, limit)
            sell_capacity = self.get_position_capacity(current_pos, False, limit)

            buy_qty = min(buy_qty, buy_capacity)
            sell_qty = min(sell_qty, sell_capacity)

            orders = []

            # Place buy order at best bid (liquidity providing)
            if buy_qty > 0:
                orders.append(Order(product, best_bid, buy_qty))

            # Place sell order at best ask (liquidity providing)
            if sell_qty > 0:
                orders.append(Order(product, best_ask, -sell_qty))

            if orders:
                result[product] = orders

        # No conversions needed for Round 3
        conversions = 0
        traderData = ""

        return result, conversions, traderData

    def bid(self) -> int:
        """Required for Round 2, ignored in Round 3."""
        return 15