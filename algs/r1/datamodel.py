# datamodel.py - Core classes from IMC Prosperity

from typing import Dict, List
import json

class Order:
    def __init__(self, symbol: str, price: int, quantity: int):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
    
    def __str__(self):
        return f"({self.symbol}, {self.price}, {self.quantity})"
    
    def __repr__(self):
        return str(self)

class OrderDepth:
    def __init__(self):
        self.buy_orders: Dict[int, int] = {}   # price -> volume
        self.sell_orders: Dict[int, int] = {}  # price -> volume

class Trade:
    def __init__(self, symbol: str, price: int, quantity: int, buyer: str = "", seller: str = "", timestamp: int = 0):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.buyer = buyer
        self.seller = seller
        self.timestamp = timestamp

class TradingState:
    def __init__(self, 
                 timestamp: int,
                 listings: Dict[str, any],
                 order_depths: Dict[str, OrderDepth],
                 own_trades: Dict[str, List[Trade]],
                 market_trades: Dict[str, List[Trade]],
                 position: Dict[str, int],
                 observations: Dict[str, any]):
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations