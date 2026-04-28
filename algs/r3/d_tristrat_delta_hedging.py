from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Tuple, Optional
import json
import math
import collections

class Trader:
    def __init__(self):
        # Position limits (correct for Round 3)
        self.position_limits = {
            'HYDROGEL_PACK': 200,
            'VELVETFRUIT_EXTRACT': 200,
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
        # Base order size per product (options get larger size)
        self.base_qty = {
            'HYDROGEL_PACK': 15,
            'VELVETFRUIT_EXTRACT': 20,
            'VEV_4000': 25,
            'VEV_4500': 25,
            'VEV_5000': 25,
            'VEV_5100': 25,
            'VEV_5200': 25,
            'VEV_5300': 25,
            'VEV_5400': 25,
            'VEV_5500': 25,
            'VEV_6000': 30,   # deep OTM, wide spread
            'VEV_6500': 30,
        }
        # Strikes for delta calculation (all VEV products)
        self.strike_map = {
            'VEV_4000': 4000, 'VEV_4500': 4500, 'VEV_5000': 5000,
            'VEV_5100': 5100, 'VEV_5200': 5200, 'VEV_5300': 5300,
            'VEV_5400': 5400, 'VEV_5500': 5500, 'VEV_6000': 6000, 'VEV_6500': 6500
        }
        # For delta calculation (simplified – assumed constant volatility)
        self.sigma = 0.3         # 30% annual vol (reasonable for VELVETFRUIT)
        self.days_to_expiry = 1.0   # options expire at end of round (1 day)
        self.r = 0.0

    # ----- Black-Scholes delta for a call option -----
    def norm_cdf(self, x: float) -> float:
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    def call_delta(self, S: float, K: float, T: float, sigma: float, r: float) -> float:
        if T <= 0:
            return 1.0 if S > K else 0.0
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        return self.norm_cdf(d1)

    def get_position_capacity(self, pos: int, is_buy: bool, limit: int) -> int:
        if is_buy:
            return max(0, limit - pos)
        else:
            return max(0, limit + pos)

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result = {}

        # ----- Get current underlying price (for delta calculation) -----
        S = 5250.0   # fallback
        if 'VELVETFRUIT_EXTRACT' in state.order_depths:
            od = state.order_depths['VELVETFRUIT_EXTRACT']
            if od.buy_orders and od.sell_orders:
                bid = max(od.buy_orders.keys())
                ask = min(od.sell_orders.keys())
                S = (bid + ask) / 2.0

        # ----- Calculate total delta from all option positions -----
        total_delta = 0.0
        for product, pos in state.position.items():
            if product in self.strike_map:
                K = self.strike_map[product]
                delta = self.call_delta(S, K, self.days_to_expiry, self.sigma, self.r)
                total_delta += delta * pos

        # Desired underlying position to be delta neutral: -total_delta
        desired_underlying = -total_delta
        current_underlying = state.position.get('VELVETFRUIT_EXTRACT', 0)
        underlying_trade = desired_underlying - current_underlying

        # ----- Market making for every product -----
        for product, order_depth in state.order_depths.items():
            if product not in self.position_limits:
                continue   # unknown product (should not happen)

            # Need both sides of the book
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            if best_bid >= best_ask:
                continue

            pos = state.position.get(product, 0)
            limit = self.position_limits[product]
            base = self.base_qty.get(product, 10)

            # Inventory skew: reduce buy size when long, reduce sell size when short
            buy_qty = base
            sell_qty = base
            if pos > 0:
                buy_qty = max(1, base // 2)
                sell_qty = min(base * 2, base + pos // 10)
            elif pos < 0:
                sell_qty = max(1, base // 2)
                buy_qty = min(base * 2, base + abs(pos) // 10)

            # Respect position limits
            buy_cap = self.get_position_capacity(pos, True, limit)
            sell_cap = self.get_position_capacity(pos, False, limit)
            buy_qty = min(buy_qty, buy_cap)
            sell_qty = min(sell_qty, sell_cap)

            orders = []
            # Place bid order (buy) at best_bid
            if buy_qty > 0:
                orders.append(Order(product, best_bid, buy_qty))
            # Place ask order (sell) at best_ask
            if sell_qty > 0:
                orders.append(Order(product, best_ask, -sell_qty))

            if orders:
                result[product] = orders

        # ----- Delta hedge: trade underlying to neutralize option delta -----
        if abs(underlying_trade) > 0.5 and 'VELVETFRUIT_EXTRACT' in state.order_depths:
            od_under = state.order_depths['VELVETFRUIT_EXTRACT']
            if od_under.buy_orders and od_under.sell_orders:
                best_bid = max(od_under.buy_orders.keys())
                best_ask = min(od_under.sell_orders.keys())
                pos_under = state.position.get('VELVETFRUIT_EXTRACT', 0)
                limit_under = self.position_limits['VELVETFRUIT_EXTRACT']
                buy_cap = self.get_position_capacity(pos_under, True, limit_under)
                sell_cap = self.get_position_capacity(pos_under, False, limit_under)

                hedge_orders = []
                if underlying_trade > 0:   # need to buy underlying
                    qty = min(int(underlying_trade + 0.5), buy_cap, 50)
                    if qty > 0:
                        hedge_orders.append(Order('VELVETFRUIT_EXTRACT', best_ask, qty))
                elif underlying_trade < 0: # need to sell underlying
                    qty = min(int(-underlying_trade + 0.5), sell_cap, 50)
                    if qty > 0:
                        hedge_orders.append(Order('VELVETFRUIT_EXTRACT', best_bid, -qty))

                if hedge_orders:
                    # Merge with existing underlying orders if any
                    if 'VELVETFRUIT_EXTRACT' in result:
                        result['VELVETFRUIT_EXTRACT'].extend(hedge_orders)
                    else:
                        result['VELVETFRUIT_EXTRACT'] = hedge_orders

        # No conversions
        conversions = 0
        traderData = json.dumps({})   # no persistent data needed
        return result, conversions, traderData

    def bid(self):
        return 15