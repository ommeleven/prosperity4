from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import statistics

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Load persistent data (price history)
        trader_data = {}
        if state.traderData:
            trader_data = json.loads(state.traderData)
        if 'price_history' not in trader_data:
            trader_data['price_history'] = []  # list of mid prices
        window = 20
        threshold = 1.5

        product = 'HYDROGEL_PACK'
        if product not in state.order_depths:
            result[product] = []
            conversions = 0
            return result, conversions, json.dumps(trader_data)

        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            result[product] = []
            conversions = 0
            return result, conversions, json.dumps(trader_data)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2.0

        # Update price history
        history = trader_data['price_history']
        history.append(mid)
        if len(history) > window * 2:
            history.pop(0)

        # Compute mean and std if enough data
        signal = None
        if len(history) >= window:
            rolling = history[-window:]
            mean = statistics.mean(rolling)
            stdev = statistics.stdev(rolling)
            zscore = (mid - mean) / stdev if stdev > 0 else 0
            if zscore > threshold:
                signal = 'sell'    # overbought, expect drop
            elif zscore < -threshold:
                signal = 'buy'     # oversold, expect rise
            # Exit if zscore crosses zero
            if abs(zscore) < 0.5:
                signal = 'exit'

        # Generate orders
        position = state.position.get(product, 0)
        limit = 200
        max_trade = 15
        orders = []
        if signal == 'buy':
            # Buy at best ask
            if position < limit:
                best_ask = min(order_depth.sell_orders.keys())
                qty = min(max_trade, limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
        elif signal == 'sell':
            # Sell at best bid
            if position > -limit:
                best_bid = max(order_depth.buy_orders.keys())
                qty = min(max_trade, position + limit)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
        elif signal == 'exit':
            # Flatten position gradually
            if position > 0:
                best_bid = max(order_depth.buy_orders.keys())
                qty = min(position, max_trade)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
            elif position < 0:
                best_ask = min(order_depth.sell_orders.keys())
                qty = min(-position, max_trade)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

        result[product] = orders

        # Save updated history
        trader_data['price_history'] = history
        traderData = json.dumps(trader_data)
        conversions = 0
        return result, conversions, traderData