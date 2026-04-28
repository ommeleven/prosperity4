from datamodel import OrderDepth, TradingState, Order, Trade
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Load persistent data (counterparty net positions)
        trader_data = {}
        if state.traderData:
            trader_data = json.loads(state.traderData)
        # Default structure
        if 'counterparty_net' not in trader_data:
            trader_data['counterparty_net'] = {}  # {counterparty: {product: net_volume}}
        if 'signal' not in trader_data:
            trader_data['signal'] = {}  # per product: 'buy'/'sell'/None

        # Update counterparty net positions from market_trades
        for product, trades in state.market_trades.items():
            for trade in trades:
                # Skip if trade involves us (buyer/seller == "SUBMISSION")
                if trade.buyer == "SUBMISSION" or trade.seller == "SUBMISSION":
                    continue
                # Identify counterparty and side
                # Trade: buyer buys from seller. So buyer increases position, seller decreases.
                # We'll track net position change from perspective of counterparty.
                for cp in [trade.buyer, trade.seller]:
                    if cp not in trader_data['counterparty_net']:
                        trader_data['counterparty_net'][cp] = {}
                    if product not in trader_data['counterparty_net'][cp]:
                        trader_data['counterparty_net'][cp][product] = 0
                # Buyer gets +quantity, seller gets -quantity
                trader_data['counterparty_net'][trade.buyer][product] += trade.quantity
                trader_data['counterparty_net'][trade.seller][product] -= trade.quantity

        # Identify smart counterparty: Mark 01 (net buyer of VELVETFRUIT_EXTRACT)
        smart_cp = None
        max_net = -1e9
        for cp, pos_dict in trader_data['counterparty_net'].items():
            net_velvet = pos_dict.get('VELVETFRUIT_EXTRACT', 0)
            if net_velvet > max_net:
                max_net = net_velvet
                smart_cp = cp
        # Similarly identify large seller: Mark 22 (net seller)
        fade_cp = None
        min_net = 1e9
        for cp, pos_dict in trader_data['counterparty_net'].items():
            net_velvet = pos_dict.get('VELVETFRUIT_EXTRACT', 0)
            if net_velvet < min_net:
                min_net = net_velvet
                fade_cp = cp

        # Generate signals for each algorithmic product
        # VELVETFRUIT_EXTRACT: follow smart_cp, fade large seller
        product = 'VELVETFRUIT_EXTRACT'
        signal = None
        if smart_cp and product in trader_data['counterparty_net'].get(smart_cp, {}):
            cp_net = trader_data['counterparty_net'][smart_cp].get(product, 0)
            if cp_net > 0:
                signal = 'buy'
            elif cp_net < 0:
                signal = 'sell'
        # Override if fading large seller (opposite signal)
        if fade_cp and product in trader_data['counterparty_net'].get(fade_cp, {}):
            cp_net = trader_data['counterparty_net'][fade_cp].get(product, 0)
            if cp_net > 0:
                signal = 'sell'   # they are buying, we sell (fade)
            elif cp_net < 0:
                signal = 'buy'    # they are selling, we buy
        trader_data['signal'][product] = signal

        # For vouchers, we can also follow smart_cp if they trade any VEV
        # But we'll keep it simple: only trade VELVETFRUIT_EXTRACT and maybe one VEV
        # Add orders
        orders = []
        # Only trade if signal exists and order depth available
        if product in state.order_depths:
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            limit = 200  # position limit
            # Determine target quantity (max 20 per step)
            max_q = 20
            if signal == 'buy':
                if position < limit:
                    # Buy at best ask or better
                    best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
                    if best_ask:
                        # Price: best_ask (immediate execution)
                        qty = min(max_q, limit - position)
                        if qty > 0:
                            orders.append(Order(product, best_ask, qty))
            elif signal == 'sell':
                if position > -limit:
                    best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
                    if best_bid:
                        qty = min(max_q, position + limit)
                        if qty > 0:
                            orders.append(Order(product, best_bid, -qty))
        result[product] = orders

        # Optional: trade one VEV (e.g., VEV_5200) using same signal
        vev_product = 'VEV_5200'   # adjust based on availability
        if vev_product in state.order_depths and signal:
            order_depth = state.order_depths[vev_product]
            position = state.position.get(vev_product, 0)
            limit = 300
            max_q = 15
            vev_orders = []
            if signal == 'buy':
                if position < limit:
                    best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
                    if best_ask:
                        qty = min(max_q, limit - position)
                        if qty > 0:
                            vev_orders.append(Order(vev_product, best_ask, qty))
            elif signal == 'sell':
                if position > -limit:
                    best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
                    if best_bid:
                        qty = min(max_q, position + limit)
                        if qty > 0:
                            vev_orders.append(Order(vev_product, best_bid, -qty))
            result[vev_product] = vev_orders

        # Persist data
        traderData = json.dumps(trader_data)
        conversions = 0
        return result, conversions, traderData