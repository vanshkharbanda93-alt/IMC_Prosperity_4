from datamodel import TradingState, Order
from typing import Dict, List


class Trader:
    POSITION_LIMITS = {"TOMATOES": 80, "EMERALDS": 80}

    def __init__(self):
        self.tomato_mid_hist = []

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

            if product == "TOMATOES":
                fair_value = self.get_tomato_fair_value(best_bid, best_ask)

                tick = 5
                skew_strength = 0
                base_size = 20

                bid_price = int(round(self.compute_bid_price(product, position, fair_value, tick, skew_strength)))
                ask_price = int(round(self.compute_ask_price(product, position, fair_value, tick, skew_strength)))

                if bid_price >= ask_price:
                    bid_price = ask_price - 1

                result[product] = self.build_orders(product, position, bid_price, ask_price, base_size)

            elif product == "EMERALDS":
                result[product] = self.trade_emeralds(order_depth, position, best_bid, best_ask)

        trader_data = ""
        conversions = 0
        return result, conversions, trader_data

    def get_tomato_fair_value(self, best_bid: int, best_ask: int) -> float:
        current_mid = (best_bid + best_ask) / 2

        self.tomato_mid_hist.append(current_mid)
        self.tomato_mid_hist = self.tomato_mid_hist[-7:]

        macro_signal = 0
        micro_signal = 0

        if len(self.tomato_mid_hist) >= 7:
            macro_move = self.tomato_mid_hist[-1] - self.tomato_mid_hist[0]

            macro_threshold = 4
            macro_shift = 3

            if macro_move > macro_threshold:
                macro_signal = macro_shift
            elif macro_move < -macro_threshold:
                macro_signal = -macro_shift

        if len(self.tomato_mid_hist) >= 4:
            mom_3 = self.tomato_mid_hist[-1] - self.tomato_mid_hist[-4]

            reversion_threshold = 2
            reversion_shift = 1

            if mom_3 > reversion_threshold:
                micro_signal = -reversion_shift
            elif mom_3 < -reversion_threshold:
                micro_signal = reversion_shift

        fair_value = current_mid + macro_signal + micro_signal
        return fair_value
    

    def trade_emeralds(self, order_depth, position: int, best_bid: int, best_ask: int) -> List[Order]: 
        # Combines passive market making with active taking
        product = "EMERALDS"
        fair_value = 10000.0
        tick = 7
        skew_strength = 0.5
        base_size = 20
        cleanup_threshold = 5
        limit = self.POSITION_LIMITS[product]

        mid = (best_bid + best_ask) / 2
        orders: List[Order] = []

        bid_price = int(round(self.compute_bid_price(product, position, fair_value, tick, skew_strength)))
        ask_price = int(round(self.compute_ask_price(product, position, fair_value, tick, skew_strength)))

        # Case 1: inventory cleanup first
        if position > cleanup_threshold and best_bid >= fair_value:
            ask_price = best_bid
            bid_price = int(round(self.compute_bid_price(product, position, fair_value, tick + 2, skew_strength)))

        elif position < -cleanup_threshold and best_ask <= fair_value:
            bid_price = best_ask
            ask_price = int(round(self.compute_ask_price(product, position, fair_value, tick + 2, skew_strength)))

        # Case 2: inventory is still moderate and mid != fair_value -- active trading
        else:
            if mid == 9996 and position < cleanup_threshold:
                take_size = min(base_size, limit - position, abs(order_depth.sell_orders[best_ask]))
                if take_size > 0:
                    orders.append(Order(product, best_ask, take_size))

            elif mid == 10004 and position > -cleanup_threshold:
                take_size = min(base_size, limit + position, order_depth.buy_orders[best_bid])
                if take_size > 0:
                    orders.append(Order(product, best_bid, -take_size))

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        remaining_buy = limit - position - sum(o.quantity for o in orders if o.quantity > 0)
        remaining_sell = limit + position - sum(-o.quantity for o in orders if o.quantity < 0)

        if remaining_buy > 0:
            orders.append(Order(product, bid_price, min(base_size, remaining_buy)))
        if remaining_sell > 0:
            orders.append(Order(product, ask_price, -min(base_size, remaining_sell)))

        return orders

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

    def compute_bid_price(self, product: str, position: int, fair_value: float, tick: int, skew_strength: float) -> float:
        inventory_pressure = position / self.POSITION_LIMITS[product]
        skew_ticks = round(inventory_pressure * skew_strength)
        return fair_value - tick - skew_ticks

    def compute_ask_price(self, product: str, position: int, fair_value: float, tick: int, skew_strength: float) -> float:
        inventory_pressure = position / self.POSITION_LIMITS[product]
        skew_ticks = round(inventory_pressure * skew_strength)
        return fair_value + tick - skew_ticks