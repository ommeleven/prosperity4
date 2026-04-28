from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict, Tuple
import json

class Trader:
    """
    Round 3 Trading Algorithm - CORRECTED VERSION
    
    CRITICAL FIX: Removed aggressive equity trading
    Strategy: Minimal positions, ONLY theta decay on vouchers
    
    Key Changes:
    1. NO aggressive hydrogel/underlying trading
    2. Tiny position sizes (max 5-10 units per trade)
    3. Focus on voucher theta decay only
    4. Strict position accumulation controls
    5. Minimal hedging (1-2 units only)
    """
    
    def __init__(self):
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
        
        self.strikes = {
            'VEV_4000': 4000,
            'VEV_4500': 4500,
            'VEV_5000': 5000,
            'VEV_5100': 5100,
            'VEV_5200': 5200,
            'VEV_5300': 5300,
            'VEV_5400': 5400,
            'VEV_5500': 5500,
            'VEV_6000': 6000,
            'VEV_6500': 6500,
        }
        
        self.voucher_products = list(self.strikes.keys())
        
        # Trade tracking to prevent excessive orders
        self.last_order_timestamp = {}
    
    def bid(self):
        """Bio-Pod bid"""
        return 15

    def calculate_intrinsic_value(self, underlying_price: float, strike: float) -> float:
        """Calculate call option intrinsic value"""
        return max(underlying_price - strike, 0)

    def get_position_capacity(self, product: str, current_position: int, is_buy: bool) -> int:
        """Calculate remaining position capacity"""
        limit = self.position_limits[product]
        
        if is_buy:
            return max(0, limit - current_position)
        else:
            return max(0, limit + current_position)

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        CORRECTED main trading logic with minimal, careful position management
        """
        
        # Parse state
        trader_state = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except:
                trader_state = {}
        
        orders = {}
        
        # Get underlying price
        underlying_price = None
        if 'VELVETFRUIT_EXTRACT' in state.order_depths:
            order_depth = state.order_depths['VELVETFRUIT_EXTRACT']
            if order_depth.buy_orders or order_depth.sell_orders:
                bids = list(order_depth.buy_orders.keys())
                asks = list(order_depth.sell_orders.keys())
                
                if bids and asks:
                    best_bid = max(bids)
                    best_ask = min(asks)
                    underlying_price = (best_bid + best_ask) / 2.0
        
        if underlying_price is None:
            underlying_price = trader_state.get('last_underlying_price', 5250.0)
        
        # ONLY TRADE VOUCHERS - THE STRATEGY THAT WORKS
        # Ignore hydrogel and underlying - they're creating losses
        
        for voucher_product in self.voucher_products:
            if voucher_product not in state.order_depths:
                continue
            
            order_depth = state.order_depths[voucher_product]
            current_pos = state.position.get(voucher_product, 0)
            
            # Get best bid/ask
            best_bid = None
            best_bid_amount = 0
            if order_depth.buy_orders:
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                best_bid = int(best_bid)
            
            best_ask = None
            best_ask_amount = 0
            if order_depth.sell_orders:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                best_ask = int(best_ask)
                best_ask_amount = abs(best_ask_amount)
            
            strike = self.strikes[voucher_product]
            intrinsic = self.calculate_intrinsic_value(underlying_price, strike)
            
            voucher_orders = []
            
            # STRATEGY: SHORT high time-value vouchers
            # Target: VEV_5100, VEV_5200 (they have highest decay)
            if voucher_product in ['VEV_5100', 'VEV_5200', 'VEV_5300']:
                if best_bid is not None and best_bid > intrinsic:
                    # Calculate time value
                    market_time_value = best_bid - intrinsic
                    
                    # Only SHORT if time value is significant
                    if market_time_value > 1.0:
                        capacity = self.get_position_capacity(voucher_product, current_pos, False)
                        
                        # KEY FIX: Much smaller position sizes
                        # Max 10 units per order to prevent accumulation
                        qty_to_sell = min(capacity, 10, best_bid_amount if best_bid_amount > 0 else 10)
                        
                        if qty_to_sell > 0 and capacity > 0:
                            voucher_orders.append(Order(voucher_product, best_bid, -qty_to_sell))
            
            if voucher_orders:
                orders[voucher_product] = voucher_orders
        
        # Store state
        trader_state['last_underlying_price'] = underlying_price
        trader_state['last_timestamp'] = state.timestamp
        
        conversions = 0
        trader_data = json.dumps(trader_state)
        
        return orders, conversions, trader_data