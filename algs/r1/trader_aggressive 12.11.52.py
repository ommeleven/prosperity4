"""
XIREN Trading Algorithm - Round 1 (AGGRESSIVE VARIANT)
Products: ASH_COATED_OSMIUM, INTARIAN_PEPPER_ROOT

Differences from base:
- ASH: tighter mm edge (3 instead of 4), lower take threshold (6 instead of 8)
  → more fills, faster inventory turnover
- IPR: tighter bid edge (3), lower take threshold (7)
  → capture more of the linear trend upside
- Larger order sizes for takes (30 instead of 20)
"""

from datamodel import (
    OrderDepth, UserId, TradingState, Order, ConversionObservation,
    Listing, Observation, Trade, ProsperityEncoder, Symbol, Product, Position
)
import json
from typing import Any


class Params:
    # ASH_COATED_OSMIUM - AGGRESSIVE
    ASH_FAIR = 10000
    ASH_MM_EDGE = 3          # tighter spread posting
    ASH_TAKE_THRESH = 6      # hit market more aggressively
    ASH_MM_QTY = 10
    ASH_TAKE_QTY = 30
    ASH_LIMIT = 80

    # INTARIAN_PEPPER_ROOT - AGGRESSIVE
    IPR_BASE = 9998.5
    IPR_DAY_OFFSET = 1000
    IPR_TICK_SLOPE = 0.001
    IPR_MM_BID_EDGE = 3      # tighter bid (fair-3 beats market bid of fair-5)
    IPR_MM_ASK_EDGE = 5      # tighter ask (fair+5 beats market ask of fair+8)
    IPR_MM_QTY = 10
    IPR_TAKE_THRESH = 7
    IPR_TAKE_QTY = 30
    IPR_LIMIT = 80


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, trader_data):
        base_length = len(self.to_json([
            self.compress_state(state, ""), self.compress_orders(orders),
            conversions, "", ""]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders), conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length)]))
        self.logs = ""

    def compress_state(self, state, trader_data):
        return [state.timestamp, trader_data,
                self.compress_listings(state.listings),
                self.compress_order_depths(state.order_depths),
                self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades),
                state.position, self.compress_observations(state.observations)]

    def compress_listings(self, listings):
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths):
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades):
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
                for arr in trades.values() for t in arr]

    def compress_observations(self, observations):
        co = {}
        for p, obs in observations.conversionObservations.items():
            co[p] = [obs.bidPrice, obs.askPrice, obs.transportFees,
                     obs.exportTariff, obs.importTariff, obs.sunlight, obs.humidity]
        return [observations.plainValueObservations, co]

    def compress_orders(self, orders):
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value):
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value, max_length):
        if len(value) <= max_length:
            return value
        return value[:max_length - 3] + "..."


logger = Logger()


def best_bid(od):
    if od.buy_orders:
        p = max(od.buy_orders)
        return p, od.buy_orders[p]
    return None, None


def best_ask(od):
    if od.sell_orders:
        p = min(od.sell_orders)
        return p, od.sell_orders[p]
    return None, None


def clamp_qty(desired, current_pos, limit):
    if desired > 0:
        return min(desired, limit - current_pos)
    else:
        return max(desired, -limit - current_pos)


def run_ash(state):
    symbol = "ASH_COATED_OSMIUM"
    if symbol not in state.order_depths:
        return []

    od = state.order_depths[symbol]
    pos = state.position.get(symbol, 0)
    p = Params
    orders = []

    bb_price, _ = best_bid(od)
    ba_price, _ = best_ask(od)
    fair = p.ASH_FAIR

    # Aggressive takes
    if ba_price is not None and ba_price < fair - p.ASH_TAKE_THRESH:
        qty = clamp_qty(p.ASH_TAKE_QTY, pos, p.ASH_LIMIT)
        if qty > 0:
            orders.append(Order(symbol, ba_price, qty))
            pos += qty

    if bb_price is not None and bb_price > fair + p.ASH_TAKE_THRESH:
        qty = clamp_qty(-p.ASH_TAKE_QTY, pos, p.ASH_LIMIT)
        if qty < 0:
            orders.append(Order(symbol, bb_price, qty))
            pos += qty

    # Multiple passive levels for more fills
    inventory_skew = -pos / p.ASH_LIMIT
    bid_skew = round(inventory_skew * 3)
    ask_skew = round(inventory_skew * 3)

    # Level 1: inside the spread
    our_bid_1 = fair - p.ASH_MM_EDGE + bid_skew
    our_ask_1 = fair + p.ASH_MM_EDGE + ask_skew

    # Level 2: slightly further out for additional depth
    our_bid_2 = fair - p.ASH_MM_EDGE - 3 + bid_skew
    our_ask_2 = fair + p.ASH_MM_EDGE + 3 + ask_skew

    buy_qty_1 = clamp_qty(p.ASH_MM_QTY, pos, p.ASH_LIMIT)
    if buy_qty_1 > 0:
        orders.append(Order(symbol, int(our_bid_1), buy_qty_1))
        pos += buy_qty_1

    buy_qty_2 = clamp_qty(p.ASH_MM_QTY, pos, p.ASH_LIMIT)
    if buy_qty_2 > 0:
        orders.append(Order(symbol, int(our_bid_2), buy_qty_2))

    sell_qty_1 = clamp_qty(-p.ASH_MM_QTY, pos, p.ASH_LIMIT)
    if sell_qty_1 < 0:
        orders.append(Order(symbol, int(our_ask_1), sell_qty_1))
        pos += sell_qty_1

    sell_qty_2 = clamp_qty(-p.ASH_MM_QTY, pos, p.ASH_LIMIT)
    if sell_qty_2 < 0:
        orders.append(Order(symbol, int(our_ask_2), sell_qty_2))

    return orders


def run_ipr(state):
    symbol = "INTARIAN_PEPPER_ROOT"
    if symbol not in state.order_depths:
        return []

    od = state.order_depths[symbol]
    pos = state.position.get(symbol, 0)
    p = Params
    orders = []

    bb_price, _ = best_bid(od)
    ba_price, _ = best_ask(od)

    if bb_price and ba_price:
        mid = (bb_price + ba_price) / 2
    elif bb_price:
        mid = bb_price + 7
    elif ba_price:
        mid = ba_price - 7
    else:
        return []

    t = state.timestamp
    day_est = round((mid - p.IPR_BASE) / p.IPR_DAY_OFFSET) - 2
    day_est = max(-2, min(10, day_est))
    fair = p.IPR_BASE + p.IPR_DAY_OFFSET * (day_est + 2) + t * p.IPR_TICK_SLOPE
    fair = round(fair, 1)

    # Aggressive takes
    if ba_price is not None and ba_price < fair - p.IPR_TAKE_THRESH:
        qty = clamp_qty(p.IPR_TAKE_QTY, pos, p.IPR_LIMIT)
        if qty > 0:
            orders.append(Order(symbol, ba_price, qty))
            pos += qty

    if bb_price is not None and bb_price > fair + p.IPR_TAKE_THRESH:
        qty = clamp_qty(-p.IPR_TAKE_QTY, pos, p.IPR_LIMIT)
        if qty < 0:
            orders.append(Order(symbol, bb_price, qty))
            pos += qty

    # Passive - two levels
    inventory_skew = -pos / p.IPR_LIMIT
    bid_skew = round(inventory_skew * 3)
    ask_skew = round(inventory_skew * 3)

    our_bid_1 = int(fair - p.IPR_MM_BID_EDGE + bid_skew)
    our_ask_1 = int(fair + p.IPR_MM_ASK_EDGE + ask_skew)
    our_bid_2 = int(fair - p.IPR_MM_BID_EDGE - 3 + bid_skew)
    our_ask_2 = int(fair + p.IPR_MM_ASK_EDGE + 3 + ask_skew)

    buy_qty_1 = clamp_qty(p.IPR_MM_QTY, pos, p.IPR_LIMIT)
    if buy_qty_1 > 0:
        orders.append(Order(symbol, our_bid_1, buy_qty_1))
        pos += buy_qty_1

    buy_qty_2 = clamp_qty(p.IPR_MM_QTY, pos, p.IPR_LIMIT)
    if buy_qty_2 > 0:
        orders.append(Order(symbol, our_bid_2, buy_qty_2))

    sell_qty_1 = clamp_qty(-p.IPR_MM_QTY, pos, p.IPR_LIMIT)
    if sell_qty_1 < 0:
        orders.append(Order(symbol, our_ask_1, sell_qty_1))
        pos += sell_qty_1

    sell_qty_2 = clamp_qty(-p.IPR_MM_QTY, pos, p.IPR_LIMIT)
    if sell_qty_2 < 0:
        orders.append(Order(symbol, our_ask_2, sell_qty_2))

    return orders


class Trader:
    def run(self, state: TradingState) -> tuple[dict, int, str]:
        result = {}
        conversions = 0

        ash_orders = run_ash(state)
        if ash_orders:
            result["ASH_COATED_OSMIUM"] = ash_orders

        ipr_orders = run_ipr(state)
        if ipr_orders:
            result["INTARIAN_PEPPER_ROOT"] = ipr_orders

        trader_data = ""
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
