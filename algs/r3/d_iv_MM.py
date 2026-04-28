import math
from typing import Dict, List, Tuple
from datamodel import Order, OrderDepth, TradingState

# -------------------------------------------------------------------------
#  Black‑Scholes helpers (no scipy → manual norm cdf approximation)
# -------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    """Abramowitz and Stegun approximation of standard normal CDF."""
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def bs_delta(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Call delta under Black‑Scholes."""
    if T <= 0:
        T = 1e-5
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return _norm_cdf(d1)


# -------------------------------------------------------------------------
#  Strategy Parameters – derived from the provided VEV market analysis
# -------------------------------------------------------------------------
VOLATILITY        = 0.5232          # annualized historical vol
TTE_DAYS          = 5.0             # time to expiry at round 3 start (days)
TTE_YEARS         = TTE_DAYS / 365   # Black‑Scholes uses yearly T
SPREAD_MIN        = 2.0             # minimum spread to quote on
INVENTORY_CAP     = 20              # max net contracts per strike for IV scalping
GAMMA_TARGET_VEV5300 = 200          # ambitious long ATM calls for gamma scalping
POS_LIMIT_VEV     = 200             # underlying VEV position limit
POS_LIMIT_VOUCHER = 300             # voucher position limit

# Strike list (VEV_x000)
STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
VEV_UNDERLYING    = "VELVETFRUIT_EXTRACT"
HYDROGEL          = "HYDROGEL_PACK"

# Sizing control
BASE_QUOTE_SIZE   = 3               # standard IV‑scalping size
WIDE_SPREAD_SIZE  = 5               # when spread ≥ $10
DELTA_TOLERANCE   = 5               # hedge only if delta drift > 5 shares


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], Dict[str, int], str]:
        """
        Core logic:
          - IV Scalping with aggressive sizes on all VEV vouchers
          - Gamma Scalping via large ATM VEV_5300 position
          - Threshold‑based delta‑hedging with VEV underlying
          - Enhanced Hydrogel spread capture
          - Automatic Ornamental Bio‑Pod liquidation
        """
        orders: Dict[str, List[Order]] = {}
        positions = state.position

        # ---- gather market data ----
        vev_book = state.order_depths.get(VEV_UNDERLYING)
        if not vev_book or not vev_book.buy_orders or not vev_book.sell_orders:
            return orders, {}, ""

        vev_best_bid = max(vev_book.buy_orders)
        vev_best_ask = min(vev_book.sell_orders)
        vev_mid = (vev_best_bid + vev_best_ask) / 2.0

        hp_book = state.order_depths.get(HYDROGEL)

        # ---- IV Scalping & Gamma Scalping on each voucher ----
        for K in STRIKES:
            symbol = f"VEV_{K}"
            book = state.order_depths.get(symbol)
            if not book or not book.buy_orders or not book.sell_orders:
                continue

            best_bid = max(book.buy_orders)
            best_ask = min(book.sell_orders)
            spread = best_ask - best_bid
            current_pos = positions.get(symbol, 0)

            # --- Gamma scalping: build large ATM position ---
            if K == 5300:
                target = GAMMA_TARGET_VEV5300
                if current_pos < target:
                    needed = min(target - current_pos, POS_LIMIT_VOUCHER - current_pos)
                    if needed > 0:
                        orders.setdefault(symbol, []).append(Order(symbol, best_ask, needed))
                    # Do NOT place selling orders while we are still accumulating
                    continue

            # --- IV Scalping (two‑sided) ---
            # Determine quote size based on spread width and inventory headroom
            base = WIDE_SPREAD_SIZE if spread >= 10.0 else BASE_QUOTE_SIZE
            # Ensure we don't exceed inventory cap when quoting both sides
            max_qty_per_side = min(base, INVENTORY_CAP - abs(current_pos))
            if max_qty_per_side <= 0:
                # Already at cap, only quote the side that reduces inventory
                if current_pos >= INVENTORY_CAP:
                    # Only sell
                    orders.setdefault(symbol, []).append(Order(symbol, best_ask, -1))
                elif current_pos <= -INVENTORY_CAP:
                    # Only buy
                    orders.setdefault(symbol, []).append(Order(symbol, best_bid, 1))
                continue

            # Place two‑sided orders only if spread is worth trading
            if spread >= SPREAD_MIN:
                orders.setdefault(symbol, []).append(Order(symbol, best_bid, max_qty_per_side))
                orders.setdefault(symbol, []).append(Order(symbol, best_ask, -max_qty_per_side))

        # ---- Global delta‑hedge with threshold ----
        total_opt_delta = 0.0
        for K in STRIKES:
            symbol = f"VEV_{K}"
            opt_pos = positions.get(symbol, 0)
            if opt_pos == 0:
                continue
            delta = bs_delta(vev_mid, K, TTE_YEARS, VOLATILITY)
            total_opt_delta += opt_pos * delta

        current_vev_pos = positions.get(VEV_UNDERLYING, 0)
        target_vev_pos = -round(total_opt_delta)          # integer shares
        target_vev_pos = max(-POS_LIMIT_VEV, min(POS_LIMIT_VEV, target_vev_pos))

        hedge_diff = target_vev_pos - current_vev_pos
        if abs(hedge_diff) > DELTA_TOLERANCE:
            if hedge_diff > 0:
                orders.setdefault(VEV_UNDERLYING, []).append(
                    Order(VEV_UNDERLYING, vev_best_ask, hedge_diff)
                )
            else:
                orders.setdefault(VEV_UNDERLYING, []).append(
                    Order(VEV_UNDERLYING, vev_best_bid, -hedge_diff)
                )

        # ---- Hydrogel Pack – aggressive spread capture ----
        if hp_book and hp_book.buy_orders and hp_book.sell_orders:
            hp_bid = max(hp_book.buy_orders)
            hp_ask = min(hp_book.sell_orders)
            hp_mid = (hp_bid + hp_ask) / 2.0
            hp_spread_pct = (hp_ask - hp_bid) / hp_mid if hp_mid > 0 else 0.0
            hp_pos = positions.get(HYDROGEL, 0)
            if hp_spread_pct > 0.02 and abs(hp_pos) < INVENTORY_CAP:
                size = 3  # up from 1
                orders.setdefault(HYDROGEL, []).append(Order(HYDROGEL, hp_bid, size))
                orders.setdefault(HYDROGEL, []).append(Order(HYDROGEL, hp_ask, -size))

        # ---- Ornamental Bio‑Pods – instant profit taking ----
        for product, depth in state.order_depths.items():
            if product == VEV_UNDERLYING or product == HYDROGEL or product.startswith("VEV_"):
                continue
            pos = positions.get(product, 0)
            if pos > 0 and depth and depth.buy_orders:
                best_bid = max(depth.buy_orders)
                orders.setdefault(product, []).append(Order(product, best_bid, -pos))
            elif pos < 0 and depth and depth.sell_orders:
                best_ask = min(depth.sell_orders)
                orders.setdefault(product, []).append(Order(product, best_ask, -pos))

        # ---- Return tuple (orders, conversions, trader_data) ----
        return orders, {}, ""