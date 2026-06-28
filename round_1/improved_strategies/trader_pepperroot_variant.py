from datamodel import TradingState, Order
from typing import Dict, List


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    def __init__(self):
        # Root fair-value tracking, kept from the original strategy
        self.root_fair: float | None = None
        self.root_slope = 0.0015
        self.root_horizon = 5000
        self.root_continuation = 0.5

        # Root spread-capture probe parameters
        self.root_target_position = 80
        self.root_min_position_after_sell = 70
        self.root_spread_threshold = 12
        self.root_probe_sell_size = 5
        self.root_aggressive_buy_size = 18
        self.root_rebuild_buy_size = 5 
        self.root_stop_selling_after = 900_000

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
                result[product] = self.trade_ash_basic_mm(
                    order_depth,
                    best_bid,
                    best_ask,
                    position,
                )

            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self.trade_root_spread_probe(
                    state.timestamp,
                    best_bid,
                    best_ask,
                    position,
                )

        trader_data = ""
        conversions = 0
        return result, conversions, trader_data

    def trade_ash_basic_mm(self, order_depth, best_bid: int, best_ask: int, position: int) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        fair_value = 10001.0
        base_size = 20
        active_base = 17
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2
        limit = self.POSITION_LIMITS[product]

        tick = self.get_ash_tick(spread)
        bid_price = int(round(mid - tick))
        ask_price = int(round(mid + tick))

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

    def trade_root_spread_probe(self, timestamp: int, best_bid: int, best_ask: int, position: int) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        limit = self.POSITION_LIMITS[product]

        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        orders: List[Order] = []

        # Keep the original trend-following fair-value estimate.
        if self.root_fair is None:
            self.root_fair = mid

        prev_fair = self.root_fair
        self.root_fair = mid + self.root_continuation * (mid - prev_fair)

        trend_boost = self.root_slope * self.root_horizon
        fair_value = self.root_fair + trend_boost

        tick = self.get_root_tick(spread)

        # This is used only for building the initial long position.
        aggressive_buy_price = int(round(fair_value - tick))
        aggressive_buy_price = min(aggressive_buy_price, best_ask)

        # 1. If we are far below the desired long position, rebuild aggressively.
        # This preserves the original buy-and-hold Root edge.
        if position < self.root_min_position_after_sell:
            buy_size = min(self.root_aggressive_buy_size, limit - position)

            if buy_size > 0:
                orders.append(Order(product, aggressive_buy_price, buy_size))

            return orders

        # 2. If we recently sold and are below the target, try to buy back passively.
        # This is the part we want to study later in the notebook.
        if position < self.root_target_position:
            buy_size = min(self.root_rebuild_buy_size, limit - position)

            if spread > 1:
                buy_price = min(best_bid + 1, best_ask - 1)
            else:
                buy_price = best_bid

            if buy_size > 0:
                orders.append(Order(product, buy_price, buy_size))

            return orders

        # 3. If we are fully long and the spread is wide, sell a small probe amount.
        # This creates controlled sell-and-buy-back events.
        if (
            position >= self.root_target_position
            and spread >= self.root_spread_threshold
            and timestamp <= self.root_stop_selling_after
        ):
            sell_size = min(
                self.root_probe_sell_size,
                position - self.root_min_position_after_sell,
            )

            if sell_size > 0:
                if spread > 1:
                    sell_price = max(best_ask - 1, best_bid + 1)
                else:
                    sell_price = best_ask

                orders.append(Order(product, sell_price, -sell_size))

        return orders

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