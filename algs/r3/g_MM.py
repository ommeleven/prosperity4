from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

class Trader:
    def __init__(self):
        # Position limits (Adjust these based on actual Round 3 limits)
        self.POS_LIMIT_OPTIONS = 50
        self.POS_LIMIT_UNDERLYING = 200

        # Assets
        self.UNDERLYING = "VELVETFRUIT_EXTRACT"
        self.GAMMA_TARGET = "VEV_5300"  # ATM Call for Gamma Scalping
        
        # IV Scalping Targets (Tier 1 & Tier 2)
        self.SCALP_TARGETS = ["VEV_5500", "VEV_5400", "VEV_5200"] 

        # Delta estimates based on Section 4.3 of the report
        self.DELTAS = {
            "VEV_5200": 0.80,  # ITM (Estimated)
            "VEV_5300": 0.50,  # ATM (Reported)
            "VEV_5400": 0.35,  # Near OTM (Estimated)
            "VEV_5500": 0.20,  # OTM (Reported)
            "VEV_6000": 0.01,  # Far OTM (Reported)
            "VEV_6500": 0.00   # Far OTM
        }

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        trader_data = state.traderData

        total_portfolio_delta = 0.0

        # ---------------------------------------------------------
        # STRATEGY 1: IV SCALPING (SPREAD CAPTURE)
        # ---------------------------------------------------------
        for symbol in self.SCALP_TARGETS:
            if symbol in state.order_depths:
                order_depth: OrderDepth = state.order_depths[symbol]
                orders: List[Order] = []
                current_pos = state.position.get(symbol, 0)
                
                # Add to our running delta tally
                total_portfolio_delta += current_pos * self.DELTAS.get(symbol, 0)

                best_bid = max(order_depth.buy_orders.keys()) if len(order_depth.buy_orders) > 0 else None
                best_ask = min(order_depth.sell_orders.keys()) if len(order_depth.sell_orders) > 0 else None

                if best_bid is not None and best_ask is not None:
                    spread = best_ask - best_bid
                    
                    # Narrow the spread if it's wide to guarantee execution (Penny jumping)
                    if spread > 2:
                        my_bid = best_bid + 1
                        my_ask = best_ask - 1
                    else:
                        my_bid = best_bid
                        my_ask = best_ask

                    # Calculate available capacity
                    buy_qty = self.POS_LIMIT_OPTIONS - current_pos
                    sell_qty = -self.POS_LIMIT_OPTIONS - current_pos

                    # Place Market Making Orders
                    if buy_qty > 0:
                        orders.append(Order(symbol, my_bid, buy_qty))
                    if sell_qty < 0:
                        orders.append(Order(symbol, my_ask, sell_qty))

                    result[symbol] = orders

        # ---------------------------------------------------------
        # STRATEGY 2: GAMMA SCALPING (ACCUMULATE CONVEXITY)
        # ---------------------------------------------------------
        if self.GAMMA_TARGET in state.order_depths:
            order_depth = state.order_depths[self.GAMMA_TARGET]
            orders = []
            current_pos = state.position.get(self.GAMMA_TARGET, 0)
            
            best_bid = max(order_depth.buy_orders.keys()) if len(order_depth.buy_orders) > 0 else None
            best_ask = min(order_depth.sell_orders.keys()) if len(order_depth.sell_orders) > 0 else None

            # We actively want to buy this to build a gamma position
            target_gamma_pos = 20 # Hold 20 contracts for gamma edge
            buy_qty = target_gamma_pos - current_pos

            if best_ask is not None and buy_qty > 0:
                # Lift the ask to accumulate the ATM position
                orders.append(Order(self.GAMMA_TARGET, best_ask, buy_qty))
                # Add expected fill to delta so we hedge it immediately
                total_portfolio_delta += (current_pos + buy_qty) * self.DELTAS.get(self.GAMMA_TARGET, 0.50)
            else:
                # If we already have our position, just track its delta
                total_portfolio_delta += current_pos * self.DELTAS.get(self.GAMMA_TARGET, 0.50)

            if len(orders) > 0:
                result[self.GAMMA_TARGET] = orders

        # ---------------------------------------------------------
        # STRATEGY 3: DELTA HEDGING (REBALANCING THE UNDERLYING)
        # ---------------------------------------------------------
        if self.UNDERLYING in state.order_depths:
            order_depth = state.order_depths[self.UNDERLYING]
            orders = []
            current_pos = state.position.get(self.UNDERLYING, 0)

            # Target position is the exact inverse of our options delta
            target_underlying_pos = -int(round(total_portfolio_delta))
            trade_qty = target_underlying_pos - current_pos

            best_bid = max(order_depth.buy_orders.keys()) if len(order_depth.buy_orders) > 0 else None
            best_ask = min(order_depth.sell_orders.keys()) if len(order_depth.sell_orders) > 0 else None

            # Execute rebalancing trades
            if trade_qty > 0 and best_ask is not None:
                # We need to get longer, buy the ask
                safe_buy_qty = min(trade_qty, self.POS_LIMIT_UNDERLYING - current_pos)
                if safe_buy_qty > 0:
                    orders.append(Order(self.UNDERLYING, best_ask, safe_buy_qty))
            
            elif trade_qty < 0 and best_bid is not None:
                # We need to get shorter, hit the bid
                safe_sell_qty = max(trade_qty, -self.POS_LIMIT_UNDERLYING - current_pos)
                if safe_sell_qty < 0:
                    orders.append(Order(self.UNDERLYING, best_bid, safe_sell_qty))

            if len(orders) > 0:
                result[self.UNDERLYING] = orders

        return result, conversions, trader_data