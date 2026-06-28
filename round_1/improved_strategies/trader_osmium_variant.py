from datamodel import TradingState, Order
from typing import Dict, List


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    def __init__(self):
        self.root_fair: float | None = None
        self.root_slope = 0.0015
        self.root_horizon = 5000
        self.root_continuation = 0.5

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            result[product] = []

            if product not in self.POSITION_LIMITS:
                continue
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            position = state.position.get(product, 0)

            if product == "ASH_COATED_OSMIUM":
                result[product] = self.trade_ash_basic_mm(order_depth, best_bid, best_ask, position)

            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self.trade_root_slope_mm(state.timestamp, best_bid, best_ask, position)

        trader_data = ""
        conversions = 0
        return result, conversions, trader_data

    def trade_ash_basic_mm(self, order_depth, best_bid: int, best_ask: int, position: int) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        #wall_mid = self.get_wall_mid(order_depth)
        fair_value = 10000 - position / 12
        base_size = 20
        active_base = 17
        #spread = best_ask - best_bid
        #mid = (best_bid + best_ask) / 2
        limit = self.POSITION_LIMITS[product]

        #tick = self.get_ash_tick(spread)
        #bid_price = int(round(mid - tick))
        #ask_price = int(round(mid + tick))

        bid_price = min(best_bid + 1, int(fair_value - 1))
        ask_price = max(best_ask - 1, int(fair_value + 1))

        orders: List[Order] = []

        buy_take_size = active_base
        sell_take_size = active_base

        if position > 20:
            sell_take_size = 17
            buy_take_size = 9
        elif position < -20:
            buy_take_size = 17
            sell_take_size = 9

        if best_ask <= fair_value:
            available_ask = abs(order_depth.sell_orders.get(best_ask, 0))
            take_size = min(buy_take_size, limit - position, available_ask)
            if take_size > 0:
                orders.append(Order(product, best_ask, take_size))

        if best_bid >= fair_value:
            available_bid = max(0, order_depth.buy_orders.get(best_bid, 0))
            take_size = min(sell_take_size, limit + position, available_bid)
            if take_size > 0:
                orders.append(Order(product, best_bid, -take_size))

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        bought_already = sum(o.quantity for o in orders if o.quantity > 0)
        sold_already = sum(-o.quantity for o in orders if o.quantity < 0)

        remaining_buy = max(0, limit - position - bought_already)
        remaining_sell = max(0, limit + position - sold_already)

        buy_size = min(base_size, remaining_buy)
        sell_size = min(base_size, remaining_sell)

        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))

        return orders

    def trade_root_slope_mm(self, timestamp: int, best_bid: int, best_ask: int, position: int) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        base_size = 18
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        if self.root_fair is None:
            self.root_fair = mid

        prev_fair = self.root_fair

        # Explicit continuation term.
        # This reproduces the same effect as using ema_alpha = 1.5:
        # new_fair = mid + 0.5 * (mid - prev_fair)
        self.root_fair = mid + self.root_continuation * (mid - prev_fair)

        trend_boost = self.root_slope * self.root_horizon
        fair_value = self.root_fair + trend_boost

        tick = self.get_root_tick(spread)
        bid_price = int(round(fair_value - tick))
        ask_price = int(round(fair_value + tick))

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        return self.build_orders(product, position, bid_price, ask_price, base_size)

    def get_ash_tick(self, spread: int) -> int:
        if spread >= 19:
            return 9
        elif spread >= 17:
            return 8
        else:
            return 7

    def get_root_tick(self, spread: int) -> int:
        if spread >= 17:
            return 7
        elif spread >= 15:
            return 6
        elif spread >= 13:
            return 5
        else:
            return 4

    def build_orders(self, product: str, position: int, bid_price: int, ask_price: int, base_size: int) -> List[Order]:
        orders: List[Order] = []

        max_buy = self.POSITION_LIMITS[product] - position
        max_sell = self.POSITION_LIMITS[product] + position

        buy_size = min(base_size, max_buy)
        sell_size = min(base_size, max_sell)

        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))

        return orders
    
    def get_wall_mid(self, order_depth):
        wall_bid = max(order_depth.buy_orders.items(), key=lambda x: x[1])[0]
        wall_ask = min(order_depth.sell_orders.items(), key=lambda x: x[1])[0]
        return (wall_bid + wall_ask) / 2