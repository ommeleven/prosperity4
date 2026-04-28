from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:

    def run(self, state: TradingState):

        result = {}

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []

            if product != "VEV_5000":
                result[product] = orders
                continue

            # --- compute fair price proxy ---
            if order_depth.sell_orders and order_depth.buy_orders:

                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())
                mid = (best_ask + best_bid) / 2

                # simplified signal logic (replace with your model)
                if mid < 100:   # placeholder regime logic
                    # BUY aggressive
                    orders.append(Order(product, best_ask, 5))

                elif mid > 200:
                    # SELL aggressive
                    orders.append(Order(product, best_bid, -5))

                else:
                    # market making
                    orders.append(Order(product, best_bid, 2))
                    orders.append(Order(product, best_ask, -2))

            result[product] = orders

        return result, 0, ""