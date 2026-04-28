from datamodel import OrderDepth, TradingState, Order, Trade
from typing import List, Dict
import json
import statistics

class Trader:
    def run(self, state: TradingState):
        result = {}

        # --- Persistent data -------------------------------------------------
        trader_data = {}
        if state.traderData:
            trader_data = json.loads(state.traderData)
        # Default structure
        if 'cp_net' not in trader_data:             # {cp: {product: net_vol}}
            trader_data['cp_net'] = {}
        if 'cp_peak' not in trader_data:            # {f"{cp}_{product}": peak_abs_net}
            trader_data['cp_peak'] = {}
        if 'mm_inv_target' not in trader_data:
            trader_data['mm_inv_target'] = {}       # per product: last target pos
        if 'cp_signal_active' not in trader_data:
            trader_data['cp_signal_active'] = {}    # per product: bool

        # --- 1. Update counterparty net positions from market_trades --------
        for product, trades in state.market_trades.items():
            for trade in trades:
                # skip our own trades
                if trade.buyer == "SUBMISSION" or trade.seller == "SUBMISSION":
                    continue
                for cp in [trade.buyer, trade.seller]:
                    if cp not in trader_data['cp_net']:
                        trader_data['cp_net'][cp] = {}
                    if product not in trader_data['cp_net'][cp]:
                        trader_data['cp_net'][cp][product] = 0
                # buyer gains +qty, seller loses -qty
                trader_data['cp_net'][trade.buyer][product] += trade.quantity
                trader_data['cp_net'][trade.seller][product] -= trade.quantity

                # update peak tracking (absolute net) - use string key
                for cp in [trade.buyer, trade.seller]:
                    net = trader_data['cp_net'][cp].get(product, 0)
                    key = f"{cp}_{product}"
                    if key not in trader_data['cp_peak']:
                        trader_data['cp_peak'][key] = abs(net)
                    else:
                        trader_data['cp_peak'][key] = max(trader_data['cp_peak'][key], abs(net))

        # --- 2. Identify counterparties to follow and fade ------------------
        # We look at VELVETFRUIT_EXTRACT as the main product for signals
        main_product = 'VELVETFRUIT_EXTRACT'
        # Gather net positions for each cp in that product
        cp_net_main = {}
        for cp, pos_dict in trader_data['cp_net'].items():
            cp_net_main[cp] = pos_dict.get(main_product, 0)

        # Find top 2 net buyers (potential smart money)
        buyers_sorted = sorted([(cp, net) for cp, net in cp_net_main.items() if net > 0],
                               key=lambda x: x[1], reverse=True)
        top_buyers = [cp for cp, _ in buyers_sorted[:2]] if buyers_sorted else []

        # Find top net seller (for fading)
        sellers_sorted = sorted([(cp, net) for cp, net in cp_net_main.items() if net < 0],
                               key=lambda x: x[1])   # most negative first
        top_seller = sellers_sorted[0][0] if sellers_sorted else None

        # Determine if we should follow the smart money (stop-loss condition)
        # Stop-loss: if any top buyer's net position has dropped more than 30% from its peak
        follow = True
        for cp in top_buyers:
            key = f"{cp}_{main_product}"
            if key in trader_data['cp_peak']:
                peak = trader_data['cp_peak'][key]
                current_abs = abs(trader_data['cp_net'].get(cp, {}).get(main_product, 0))
                if peak > 0 and current_abs / peak < 0.7:   # dropped >30%
                    follow = False
                    break

        # Generate signal for main_product: buy if following smart buyers and net > 0
        signal = None
        if follow and top_buyers:
            # average net of top buyers
            avg_net = sum(trader_data['cp_net'].get(cp, {}).get(main_product, 0) for cp in top_buyers) / len(top_buyers)
            if avg_net > 50:
                signal = 'buy'
            elif avg_net < -50:
                signal = 'sell'
        # Override with fade signal if top seller is huge (net < -1000)
        if top_seller and trader_data['cp_net'].get(top_seller, {}).get(main_product, 0) < -1000:
            # fade: they are selling heavily, so we buy
            signal = 'buy'

        # Store signal for use later (and for other products)
        trader_data['cp_signal_active'][main_product] = signal

        # --- 3. Apply signal to VELVETFRUIT_EXTRACT (if any) -----------------
        if main_product in state.order_depths and signal:
            orders = self._trade_signal(state, main_product, signal, limit=200, max_q=20)
            if orders:
                result[main_product] = orders

        # --- 4. Market making on VEV_5200 and VEV_5100 (scaled up) ----------
        mm_products = ['VEV_5200', 'VEV_5100']
        for product in mm_products:
            if product not in state.order_depths:
                continue
            order_depth = state.order_depths[product]
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            bid_vol = order_depth.buy_orders[best_bid]
            ask_vol = -order_depth.sell_orders[best_ask]
            spread = best_ask - best_bid
            if spread > 10:   # only market make when spread reasonable
                continue

            position = state.position.get(product, 0)
            limit = 300
            # Increased base quantity from 10 to 25
            base_qty = 25
            # Aggressive skew: adjust price and quantity based on inventory
            skew = position // 10   # stronger skew than before (/10 instead of /20)
            # Adjust bid/ask prices
            bid_price = best_bid + 1 - min(5, max(-5, skew))
            ask_price = best_ask - 1 - min(5, max(-5, skew))
            # Ensure bid < ask
            if bid_price >= ask_price:
                bid_price = best_bid
                ask_price = best_ask

            # Quantities: reduce if near limit, but keep higher base
            buy_qty = base_qty
            sell_qty = base_qty
            if position + buy_qty > limit:
                buy_qty = max(0, limit - position)
            if position - sell_qty < -limit:
                sell_qty = max(0, position + limit)

            orders = []
            if buy_qty > 0:
                orders.append(Order(product, bid_price, buy_qty))
            if sell_qty > 0:
                orders.append(Order(product, ask_price, -sell_qty))
            if orders:
                result[product] = orders
                # update inventory target (for next iteration, though not strictly needed)
                trader_data['mm_inv_target'][product] = position + (buy_qty - sell_qty)

        # --- 5. Optionally apply counterparty signal to VEV_5200 as well -----
        # If we have a strong buy/sell signal from counterparty, we can also trade VEV_5200
        # to amplify profit, but do it carefully to not blow position limits.
        if signal and signal in ['buy', 'sell'] and 'VEV_5200' in state.order_depths:
            vev_orders = self._trade_signal(state, 'VEV_5200', signal, limit=300, max_q=15)
            if vev_orders:
                # Merge with existing orders for VEV_5200 (if any from MM)
                if 'VEV_5200' in result:
                    result['VEV_5200'].extend(vev_orders)
                else:
                    result['VEV_5200'] = vev_orders

        # --- 6. Clean up traderData to avoid unlimited growth --------------
        # Keep only last 20 counterparties? Not strictly needed, but we can limit cp_net keys
        # For simplicity, leave as is; serialization will handle strings.
        traderData = json.dumps(trader_data)
        conversions = 0
        return result, conversions, traderData

    # Helper to generate buy/sell orders based on signal
    def _trade_signal(self, state: TradingState, product: str, signal: str, limit: int, max_q: int):
        order_depth = state.order_depths[product]
        position = state.position.get(product, 0)
        orders = []
        if signal == 'buy':
            if position < limit and order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                qty = min(max_q, limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
        elif signal == 'sell':
            if position > -limit and order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                qty = min(max_q, position + limit)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
        return orders