
from datamodel import TradingState, Order
from typing import Dict, List, Tuple
import math
import json


class Trader:
    POSITION_LIMITS = {
        "VELVETFRUIT_EXTRACT": 200,
        "HYDROGEL_PACK": 200,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
    }

    OPTION_STRIKES = {
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
    }

    # Histogram-based priors only stabilize the live smile fit.
    PRIOR_IV = {
        "VEV_5000": 0.236,
        "VEV_5100": 0.229,
        "VEV_5200": 0.235,
        "VEV_5300": 0.236,
    }

    OPTION_SOFT_LIMIT = 300 #80
    OPTION_TTE_DAYS = 5.0

    def __init__(self):
        pass

    def bid(self):
        return 0

    def run(self, state: TradingState):
        # Keep only small state for VFE fair estimation.
        data = self.load_data(state.traderData)
        result: Dict[str, List[Order]] = {}

        # First compute live VFE fair. Options use this as the underlying fair.
        vfe_fair = None
        vfe_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if vfe_depth and vfe_depth.buy_orders and vfe_depth.sell_orders:
            vfe_best_bid = max(vfe_depth.buy_orders.keys())
            vfe_best_ask = min(vfe_depth.sell_orders.keys())
            vfe_mid = (vfe_best_bid + vfe_best_ask) / 2
            vfe_micro = self.get_microprice(vfe_depth, vfe_best_bid, vfe_best_ask)

            data["vfe_fast_ema"] = self.update_ema(data.get("vfe_fast_ema"), vfe_mid, 0.18)
            data["vfe_slow_ema"] = self.update_ema(data.get("vfe_slow_ema"), vfe_mid, 0.05)

            # Same VFE fair logic as the fixed delta-1 base.
            vfe_fair = 0.45 * vfe_micro + 0.35 * data["vfe_fast_ema"] + 0.20 * data["vfe_slow_ema"]

        # Build a live fitted IV smile from the middle strikes only.
        smile = None
        if vfe_fair is not None:
            smile = self.build_live_smile(state, vfe_fair)

        for product, order_depth in state.order_depths.items():
            result[product] = []

            if product == "VELVETFRUIT_EXTRACT":
                if order_depth.buy_orders and order_depth.sell_orders and vfe_fair is not None:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_ask = min(order_depth.sell_orders.keys())
                    position = state.position.get(product, 0)

                    result[product] = self.trade_vfe_value_hybrid(
                        order_depth,
                        best_bid,
                        best_ask,
                        position,
                        vfe_fair,
                    )

            elif product == "HYDROGEL_PACK":
                if order_depth.buy_orders and order_depth.sell_orders:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_ask = min(order_depth.sell_orders.keys())
                    position = state.position.get(product, 0)

                    # Keep Hydrogel unchanged from the fixed delta-1 base.
                    result[product] = self.trade_hp_basic_mm(best_bid, best_ask, position)

            elif product in self.OPTION_STRIKES:
                if order_depth.buy_orders and order_depth.sell_orders and vfe_fair is not None and smile is not None:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_ask = min(order_depth.sell_orders.keys())
                    position = state.position.get(product, 0)

                    result[product] = self.trade_option_smile(
                        product,
                        order_depth,
                        best_bid,
                        best_ask,
                        position,
                        vfe_fair,
                        smile,
                    )

        trader_data = json.dumps(data)
        return result, 0, trader_data

    # -------------------------
    # Fixed delta-1 base
    # -------------------------
    def trade_vfe_value_hybrid(
        self,
        order_depth,
        best_bid: int,
        best_ask: int,
        position: int,
        fair_value: float,
    ) -> List[Order]:
        product = "VELVETFRUIT_EXTRACT"
        spread = best_ask - best_bid
        orders: List[Order] = []

        # Keep the same spread filter as the best base.
        if spread < 5:
            return orders

        reservation = fair_value - 0.05 * position
        tick = self.get_vfe_tick(spread)

        buy_value = math.floor(reservation - tick)
        sell_value = math.ceil(reservation + tick)

        # Take now if the touch is already at our value.
        take_buy_cap, take_sell_cap = self.get_vfe_take_sizes(position, spread)

        for ask_price in sorted(order_depth.sell_orders.keys()):
            ask_volume = -order_depth.sell_orders[ask_price]
            if ask_price > buy_value:
                break

            buy_qty = min(
                ask_volume,
                take_buy_cap - self.current_buy_qty(orders),
                self.POSITION_LIMITS[product] - position - self.current_buy_qty(orders),
            )
            if buy_qty > 0:
                orders.append(Order(product, ask_price, buy_qty))

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            bid_volume = order_depth.buy_orders[bid_price]
            if bid_price < sell_value:
                break

            sell_qty = min(
                bid_volume,
                take_sell_cap - self.current_sell_qty(orders),
                self.POSITION_LIMITS[product] + position - self.current_sell_qty(orders),
            )
            if sell_qty > 0:
                orders.append(Order(product, bid_price, -sell_qty))

        expected_position = position + self.current_buy_qty(orders) - self.current_sell_qty(orders)

        reservation = fair_value - 0.05 * expected_position
        bid_price = math.floor(reservation - tick)
        ask_price = math.ceil(reservation + tick)

        # Stay passive after taking.
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if bid_price >= ask_price:
            ask_price = bid_price + 1

        buy_size, sell_size = self.get_vfe_passive_sizes(expected_position)
        orders += self.build_orders(product, expected_position, bid_price, ask_price, buy_size, sell_size)
        return orders

    def trade_hp_basic_mm(self, best_bid: int, best_ask: int, position: int) -> List[Order]:
        product = "HYDROGEL_PACK"
        base_size = 25
        spread = best_ask - best_bid
        fair_value = 9957.5

        if spread < 15:
            return []

        tick = self.get_hp_tick(spread)
        bid_price = math.floor(fair_value - tick)
        ask_price = math.ceil(fair_value + tick)

        return self.build_orders(product, position, bid_price, ask_price, base_size, base_size)

    # -------------------------
    # Options: live smile + BS fair + residual trading
    # -------------------------
    def build_live_smile(self, state: TradingState, vfe_fair: float):
        # Fit only the cleaner middle strikes.
        points = []

        for product, strike in self.OPTION_STRIKES.items():
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())
            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

            iv = self.implied_vol_call(
                price=mid,
                spot=vfe_fair,
                strike=strike,
                t=self.OPTION_TTE_DAYS / 365.0,
            )

            if iv is None:
                continue

            # Use log-moneyness and weight tighter strikes a bit more.
            x = math.log(max(vfe_fair, 1.0) / strike)
            w = 1.0 / max(1.0, float(spread))
            points.append((x, iv, w))

        # Need at least 3 points for a stable quadratic smile.
        if len(points) < 3:
            return None

        return self.weighted_quadratic_fit(points)

    def trade_option_smile(
        self,
        product: str,
        order_depth,
        best_bid: int,
        best_ask: int,
        position: int,
        vfe_fair: float,
        smile,
    ) -> List[Order]:
        strike = self.OPTION_STRIKES[product]
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2
        orders: List[Order] = []

        # Skip strange books.
        if spread <= 0 or spread > 8:
            return orders

        t = self.OPTION_TTE_DAYS / 365.0
        x = math.log(max(vfe_fair, 1.0) / strike)

        # Live fitted smile.
        fit_iv = self.eval_quadratic(smile, x)

        # Pull slightly toward the historical prior to reduce noise.
        fit_iv = 0.70 * fit_iv + 0.30 * self.PRIOR_IV[product]
        fit_iv = min(max(fit_iv, 0.15), 0.45)

        fair_price = self.bs_call_price(vfe_fair, strike, t, fit_iv)
        obs_iv = self.implied_vol_call(mid, vfe_fair, strike, t)

        if obs_iv is None:
            return orders

        iv_resid = obs_iv - fit_iv

        # Buffers depend on how wide the strike usually is.
        price_buffer = max(1.0, 0.40 * spread)
        iv_buffer = 0.004

        # Internal soft limit keeps the first overlay conservative.
        soft_limit = self.OPTION_SOFT_LIMIT

        # Active trade only if both price and IV residual agree.
        if iv_resid < -iv_buffer and best_ask <= fair_price - price_buffer:
            buy_qty = min(
                -order_depth.sell_orders[best_ask],
                self.get_option_take_size(product, position, buy_side=True),
                soft_limit - position,
            )
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty

        if iv_resid > iv_buffer and best_bid >= fair_price + price_buffer:
            sell_qty = min(
                order_depth.buy_orders[best_bid],
                self.get_option_take_size(product, position, buy_side=False),
                soft_limit + position,
            )
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty

        # Quote passively around fair after any active trade.
        reservation = fair_price - self.get_option_inventory_skew(product) * position
        half_width = self.get_option_half_width(product, spread)

        bid_price = math.floor(reservation - half_width)
        ask_price = math.ceil(reservation + half_width)

        # Stay passive around the current book.
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if bid_price >= ask_price:
            ask_price = bid_price + 1

        buy_size, sell_size = self.get_option_passive_sizes(product, position, soft_limit)
        orders += self.build_orders_soft(product, position, bid_price, ask_price, buy_size, sell_size, soft_limit)
        return orders

    # -------------------------
    # Sizing helpers
    # -------------------------
    def get_vfe_take_sizes(self, position: int, spread: int) -> Tuple[int, int]:
        base = 8 if spread == 5 else 10

        if position >= 120:
            return 2, base + 2
        if position >= 60:
            return 4, base + 1
        if position <= -120:
            return base + 2, 2
        if position <= -60:
            return base + 1, 4
        return base, base

    def get_vfe_passive_sizes(self, position: int) -> Tuple[int, int]:
        if position >= 120:
            return 10, 42
        if position >= 60:
            return 18, 36
        if position <= -120:
            return 42, 10
        if position <= -60:
            return 36, 18
        return 30, 30

    def get_option_take_size(self, product: str, position: int, buy_side: bool) -> int:
        base = {
            "VEV_5000": 8,
            "VEV_5100": 8,
            "VEV_5200": 10,
            "VEV_5300": 10,
        }[product]

        # Reduce taking on the side that worsens inventory.
        if buy_side and position > 40:
            return max(2, base - 4)
        if (not buy_side) and position < -40:
            return max(2, base - 4)
        return base

    def get_option_passive_sizes(self, product: str, position: int, soft_limit: int) -> Tuple[int, int]:
        base = {
            "VEV_5000": 10,
            "VEV_5100": 10,
            "VEV_5200": 12,
            "VEV_5300": 12,
        }[product]

        if position >= soft_limit * 0.75:
            return 3, base + 5
        if position >= soft_limit * 0.35:
            return 6, base + 3
        if position <= -soft_limit * 0.75:
            return base + 5, 3
        if position <= -soft_limit * 0.35:
            return base + 3, 6
        return base, base

    def get_option_half_width(self, product: str, spread: int) -> float:
        # Use the observed spread regime for each strike.
        if product == "VEV_5000":
            return 3.0 if spread >= 6 else 2.0
        if product == "VEV_5100":
            return 2.0 if spread >= 4 else 1.5
        if product == "VEV_5200":
            return 1.5 if spread >= 3 else 1.0
        return 1.0

    def get_option_inventory_skew(self, product: str) -> float:
        return {
            "VEV_5000": 0.030,
            "VEV_5100": 0.026,
            "VEV_5200": 0.022,
            "VEV_5300": 0.020,
        }[product]

    def get_vfe_tick(self, spread: int) -> int:
        return 2 if spread >= 6 else 1

    def get_hp_tick(self, spread: int) -> int:
        return 7 if spread >= 16 else 6

    # -------------------------
    # Generic order helpers
    # -------------------------
    def build_orders(
        self,
        product: str,
        position: int,
        bid_price: int,
        ask_price: int,
        buy_size: int,
        sell_size: int,
    ) -> List[Order]:
        orders: List[Order] = []

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        max_buy = self.POSITION_LIMITS[product] - position
        max_sell = self.POSITION_LIMITS[product] + position

        buy_size = min(buy_size, max_buy)
        sell_size = min(sell_size, max_sell)

        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))

        return orders

    def build_orders_soft(
        self,
        product: str,
        position: int,
        bid_price: int,
        ask_price: int,
        buy_size: int,
        sell_size: int,
        soft_limit: int,
    ) -> List[Order]:
        orders: List[Order] = []

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        max_buy = min(self.POSITION_LIMITS[product], soft_limit) - position
        max_sell = min(self.POSITION_LIMITS[product], soft_limit) + position

        buy_size = min(buy_size, max_buy)
        sell_size = min(sell_size, max_sell)

        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))

        return orders

    def current_buy_qty(self, orders: List[Order]) -> int:
        return sum(o.quantity for o in orders if o.quantity > 0)

    def current_sell_qty(self, orders: List[Order]) -> int:
        return sum(-o.quantity for o in orders if o.quantity < 0)

    # -------------------------
    # Fair-value / model helpers
    # -------------------------
    def get_microprice(self, order_depth, best_bid: int, best_ask: int) -> float:
        # Use best bid/ask sizes to tilt fair slightly.
        bid_vol = order_depth.buy_orders.get(best_bid, 0)
        ask_vol = -order_depth.sell_orders.get(best_ask, 0)
        denom = bid_vol + ask_vol

        if denom <= 0:
            return (best_bid + best_ask) / 2

        return (best_bid * ask_vol + best_ask * bid_vol) / denom

    def update_ema(self, old_value, new_value: float, alpha: float) -> float:
        if old_value is None:
            return float(new_value)
        return (1 - alpha) * old_value + alpha * new_value

    def bs_call_price(self, spot: float, strike: float, t: float, sigma: float) -> float:
        # Zero-rate Black-Scholes call.
        if sigma <= 1e-8 or t <= 1e-8:
            return max(0.0, spot - strike)

        vol = sigma * math.sqrt(t)
        if vol <= 1e-12:
            return max(0.0, spot - strike)

        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol
        d2 = d1 - vol
        return spot * self.norm_cdf(d1) - strike * self.norm_cdf(d2)

    def implied_vol_call(self, price: float, spot: float, strike: float, t: float):
        # Simple bisection. Good enough for this competition.
        intrinsic = max(0.0, spot - strike)
        upper_price = spot

        if price <= intrinsic + 1e-8:
            return 0.0001
        if price >= upper_price - 1e-8:
            return None

        lo, hi = 0.0001, 3.0
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            mid_price = self.bs_call_price(spot, strike, t, mid)

            if mid_price > price:
                hi = mid
            else:
                lo = mid

        return 0.5 * (lo + hi)

    def norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def weighted_quadratic_fit(self, points: List[Tuple[float, float, float]]):
        # Fit y = a + b x + c x^2 using weighted least squares.
        s0 = sx = sx2 = sx3 = sx4 = sy = sxy = sx2y = 0.0

        for x, y, w in points:
            x2 = x * x
            s0 += w
            sx += w * x
            sx2 += w * x2
            sx3 += w * x2 * x
            sx4 += w * x2 * x2
            sy += w * y
            sxy += w * x * y
            sx2y += w * x2 * y

        return self.solve_3x3(
            s0, sx, sx2, sy,
            sx, sx2, sx3, sxy,
            sx2, sx3, sx4, sx2y,
        )

    def solve_3x3(self, a11, a12, a13, b1, a21, a22, a23, b2, a31, a32, a33, b3):
        # Tiny Gaussian elimination for the normal equations.
        m = [
            [a11, a12, a13, b1],
            [a21, a22, a23, b2],
            [a31, a32, a33, b3],
        ]

        for i in range(3):
            pivot = i
            for j in range(i + 1, 3):
                if abs(m[j][i]) > abs(m[pivot][i]):
                    pivot = j
            m[i], m[pivot] = m[pivot], m[i]

            if abs(m[i][i]) < 1e-12:
                # Fallback to a flat smile if the system is singular.
                avg = (b1 + b2 + b3) / 3.0
                return (avg, 0.0, 0.0)

            div = m[i][i]
            for k in range(i, 4):
                m[i][k] /= div

            for j in range(3):
                if j == i:
                    continue
                factor = m[j][i]
                for k in range(i, 4):
                    m[j][k] -= factor * m[i][k]

        return (m[0][3], m[1][3], m[2][3])

    def eval_quadratic(self, coeffs, x: float) -> float:
        a, b, c = coeffs
        return a + b * x + c * x * x

    # -------------------------
    # State helper
    # -------------------------
    def load_data(self, trader_data: str) -> dict:
        if not trader_data:
            return {"vfe_fast_ema": None, "vfe_slow_ema": None}
        try:
            data = json.loads(trader_data)
            data.setdefault("vfe_fast_ema", None)
            data.setdefault("vfe_slow_ema", None)
            return data
        except Exception:
            return {"vfe_fast_ema": None, "vfe_slow_ema": None}
