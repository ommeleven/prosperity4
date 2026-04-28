from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import math
import jsonpickle

class Trader:
    def __init__(self):
        # EMA parameters
        self.ema_alpha = 0.1
        
        # Extrapolated Time Value (Premium) for TTE = 5 (Round 3)
        self.option_premiums = {
            4000: 0.0,
            4500: 0.0,
            5000: 1.5,
            5100: 7.5,
            5200: 30.5,
            5300: 42.0,
            5400: 11.8,
            5500: 4.0,
            6000: 0.5,
            6500: 0.5
        }
        
        # Position Limits
        self.limits = {
            "HYDROGEL_PACK": 200,
            "VELVETFRUIT_EXTRACT": 200,
            "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300,
            "VEV_5100": 300, "VEV_5200": 300, "VEV_5300": 300,
            "VEV_5400": 300, "VEV_5500": 300, "VEV_6000": 300,
            "VEV_6500": 300
        }

    def compute_mid_price(self, order_depth: OrderDepth) -> float:
        if len(order_depth.sell_orders) > 0 and len(order_depth.buy_orders) > 0:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            return (best_ask + best_bid) / 2.0
        return None

    def run(self, state: TradingState):
        result = {}
        
        # Restore state data (EMA)
        trader_state = {}
        if state.traderData:
            try:
                trader_state = jsonpickle.decode(state.traderData)
            except:
                pass
                
        emas = trader_state.get("emas", {})

        # 1. First, update EMAs and find the underlying price
        underlying_price = None
        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            mid = self.compute_mid_price(state.order_depths["VELVETFRUIT_EXTRACT"])
            if mid is not None:
                underlying_price = mid
                if "VELVETFRUIT_EXTRACT" not in emas:
                    emas["VELVETFRUIT_EXTRACT"] = mid
                else:
                    emas["VELVETFRUIT_EXTRACT"] = self.ema_alpha * mid + (1 - self.ema_alpha) * emas["VELVETFRUIT_EXTRACT"]

        if "HYDROGEL_PACK" in state.order_depths:
            mid = self.compute_mid_price(state.order_depths["HYDROGEL_PACK"])
            if mid is not None:
                if "HYDROGEL_PACK" not in emas:
                    emas["HYDROGEL_PACK"] = mid
                else:
                    emas["HYDROGEL_PACK"] = self.ema_alpha * mid + (1 - self.ema_alpha) * emas["HYDROGEL_PACK"]

        # 2. Strategy for Delta-1 Products (Market Making)
        for product in ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT"]:
            if product in state.order_depths and product in emas:
                order_depth = state.order_depths[product]
                orders: List[Order] = []
                
                pos = state.position.get(product, 0)
                limit = self.limits[product]
                
                fair_val = emas[product]
                
                # Dynamic spread based on inventory
                buy_price = math.floor(fair_val - 1.5 - (pos / limit) * 2)
                sell_price = math.ceil(fair_val + 1.5 - (pos / limit) * 2)
                
                buy_qty = limit - pos
                sell_qty = -limit - pos
                
                # Take aggressive trades if market is out of whack
                if len(order_depth.sell_orders) != 0:
                    best_ask = min(order_depth.sell_orders.keys())
                    best_ask_vol = order_depth.sell_orders[best_ask]
                    if best_ask < fair_val - 1:
                        take_qty = min(buy_qty, -best_ask_vol)
                        if take_qty > 0:
                            orders.append(Order(product, best_ask, take_qty))
                            buy_qty -= take_qty
                            pos += take_qty

                if len(order_depth.buy_orders) != 0:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_bid_vol = order_depth.buy_orders[best_bid]
                    if best_bid > fair_val + 1:
                        take_qty = max(sell_qty, -best_bid_vol)
                        if take_qty < 0:
                            orders.append(Order(product, best_bid, take_qty))
                            sell_qty -= take_qty
                            pos += take_qty
                
                # Provide liquidity
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
                if sell_qty < 0:
                    orders.append(Order(product, sell_price, sell_qty))
                    
                result[product] = orders

        # 3. Strategy for Options (Vouchers)
        if underlying_price is not None:
            for product in state.order_depths:
                if product.startswith("VEV_"):
                    strike = int(product.split("_")[1])
                    order_depth = state.order_depths[product]
                    orders: List[Order] = []
                    
                    pos = state.position.get(product, 0)
                    limit = self.limits[product]
                    
                    # Calculate Fair Value
                    intrinsic_value = max(underlying_price - strike, 0)
                    time_value = self.option_premiums.get(strike, 0)
                    fair_value = intrinsic_value + time_value
                    
                    edge = 1.0 # Minimum profit margin to cross spread
                    
                    # Buy undervalued options
                    if len(order_depth.sell_orders) != 0:
                        for ask_price, ask_vol in sorted(order_depth.sell_orders.items()):
                            if ask_price < fair_value - edge:
                                buy_vol = min(limit - pos, -ask_vol)
                                if buy_vol > 0:
                                    orders.append(Order(product, ask_price, buy_vol))
                                    pos += buy_vol
                            else:
                                break

                    # Sell overvalued options
                    if len(order_depth.buy_orders) != 0:
                        for bid_price, bid_vol in sorted(order_depth.buy_orders.items(), reverse=True):
                            if bid_price > fair_value + edge:
                                sell_vol = max(-limit - pos, -bid_vol)
                                if sell_vol < 0:
                                    orders.append(Order(product, bid_price, sell_vol))
                                    pos += sell_vol
                            else:
                                break
                    
                    if orders:
                        result[product] = orders

        trader_state["emas"] = emas
        traderData = jsonpickle.encode(trader_state)
        
        # No automated conversion logic needed specifically, handled by liquidation
        conversions = 0
        return result, conversions, traderData