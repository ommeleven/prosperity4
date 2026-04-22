import json
from typing import Any, Dict, List

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


# ================= LOGGER (FIXED) =================
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list:
        compressed = []
        for arr in trades.values():
            for t in arr:
                compressed.append([t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp])
        return compressed

    def compress_observations(self, observations: Observation) -> list:
        conversion_observations = {}
        for p, o in observations.conversionObservations.items():
            conversion_observations[p] = [
                o.bidPrice,
                o.askPrice,
                o.transportFees,
                o.exportTariff,
                o.importTariff,
                o.sugarPrice,
                o.sunlightIndex,
            ]
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[:max_length - 3] + "..."


logger = Logger()


# ================= TRADER =================
class Trader:

    def __init__(self):
        self.position_limit = 20

    def run(self, state: TradingState) -> tuple[Dict[Symbol, List[Order]], int, str]:

        result = {}
        conversions = 0
        trader_data = ""

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []

            if len(order_depth.buy_orders) == 0 or len(order_depth.sell_orders) == 0:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            mid_price = (best_bid + best_ask) / 2
            position = state.position.get(product, 0)

            spread = best_ask - best_bid

            # ===== LOG IMPORTANT INFO =====
            logger.print(
                f"{product} | pos={position} bid={best_bid} ask={best_ask} mid={mid_price} spread={spread}"
            )

            # ===== INVENTORY SKEW =====
            skew = position * 0.1

            buy_price = int(mid_price - 1 - skew)
            sell_price = int(mid_price + 1 - skew)

            size = max(1, 5 - abs(position))

            # ===== PASSIVE MARKET MAKING =====
            if position < self.position_limit:
                orders.append(Order(product, buy_price, size))

            if position > -self.position_limit:
                orders.append(Order(product, sell_price, -size))

            # ===== AGGRESSIVE TRADES (MISPRICING) =====
            if best_ask < mid_price:
                orders.append(Order(product, best_ask, min(3, self.position_limit - position)))

            if best_bid > mid_price:
                orders.append(Order(product, best_bid, -min(3, self.position_limit + position)))

            result[product] = orders

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data