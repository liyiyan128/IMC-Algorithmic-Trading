import numpy as np
import statistics
import jsonpickle
from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order, Trade


class Trader:
    def __init__(self):
        self.POSITION_LIMIT = 50

    def take_best_orders(
            self, product: str, position: int,
            fair_value: int, spread: int,
            order_depth: OrderDepth, orders: List[Order],
            buy_order_volume: int = 0, sell_order_volume: int = 0
    ) -> Tuple[int, int]:
        # Buy orders
        if len(order_depth.sell_orders) > 0:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_qty = order_depth.sell_orders[best_ask]
            if best_ask <= fair_value - spread:  # underpriced
                qty = min(best_ask_qty, self.POSITION_LIMIT-position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    print(f"[SUBMIT] BUY {qty} {product} @ {best_ask}")
                    buy_order_volume += qty
                    order_depth.sell_orders[best_ask] -= qty
                    if order_depth.sell_orders[best_ask] == 0:
                        del order_depth.sell_orders[best_ask]
        # Sell orders
        if len(order_depth.buy_orders) > 0:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_qty = order_depth.buy_orders[best_bid]
            if best_bid >= fair_value + spread:  # overpriced
                qty = min(best_bid_qty, self.POSITION_LIMIT+position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    print(f"[SUBMIT] SELL {qty} {product} @ {best_bid}")
                    sell_order_volume += qty
                    order_depth.buy_orders[best_bid] -= qty
                    if order_depth.buy_orders[best_bid] == 0:
                        del order_depth.buy_orders[best_bid]
        return buy_order_volume, sell_order_volume

    def clear_position_orders(
        self, product: str, position: int,
        fair_value: float, spread: float,
        order_depth: OrderDepth, orders: List[Order],
        buy_order_volume: int, sell_order_volume: int,
    ) -> Tuple[int, int]:
        cur_position = position + buy_order_volume - sell_order_volume
        our_bid = int(round(fair_value - spread))
        our_ask = int(round(fair_value + spread))

        max_buy_qty = self.POSITION_LIMIT - (position + buy_order_volume)
        max_sell_qty = self.POSITION_LIMIT + (position - sell_order_volume)

        if cur_position > 0:
            qty = sum(
                volume
                for price, volume in order_depth.buy_orders.items()
                if price >= our_ask
            )
            qty = min((qty, cur_position, max_sell_qty))
            if qty > 0:
                orders.append(Order(product, our_ask, -abs(qty)))
                print(f"[SUBMIT] SELL {abs(qty)} {product} @ {our_ask}")
                sell_order_volume += abs(qty)
        if cur_position < 0:
            qty = sum(
                volume
                for price, volume in order_depth.sell_orders.items()
                if price <= our_bid
            )
            qty = min((qty, -cur_position, max_buy_qty))
            if qty > 0:
                orders.append(Order(product, our_bid, abs(qty)))
                print(f"[SUBMIT] BUY {abs(qty)} {product} @ {our_bid}")
                buy_order_volume += abs(qty)

        return buy_order_volume, sell_order_volume

    def make_market(
        self, product: str, position: int, fair_value: float,
        ignore_spread: float,  # ignore orders too close to fair value
        match_spread: float,  # match orders within this spread
        base_spread: float,
        order_depth: OrderDepth, orders: List[Order],
        buy_order_volume: int, sell_order_volume: int,
        INVENTORY_SOFT_LIMIT: int,
    ):
        best_ask_above_fair = min(
            (price for price in order_depth.sell_orders.keys()
             if price > fair_value + ignore_spread), default=0)
        best_bid_below_fair = max(
            (price for price in order_depth.buy_orders.keys()
             if price < fair_value - ignore_spread), default=0)
        our_ask = round(fair_value + base_spread)
        our_bid = round(fair_value - base_spread)

        if best_ask_above_fair > 0:
            if abs(best_ask_above_fair - fair_value) <= match_spread:
                our_ask = best_ask_above_fair  # match price
            else:
                our_ask = best_ask_above_fair - 1 # penny
        if best_bid_below_fair > 0:
            if abs(best_bid_below_fair - fair_value) <= match_spread:
                our_bid = best_bid_below_fair
            else:
                our_bid = best_bid_below_fair + 1

        if position > INVENTORY_SOFT_LIMIT:
            our_ask -= 1
        if position < -INVENTORY_SOFT_LIMIT:
            our_bid += 1

        buy_qty = self.POSITION_LIMIT - (position + buy_order_volume)
        sell_qty = self.POSITION_LIMIT + (position - sell_order_volume)
        if buy_qty > 0:
            orders.append(Order(product, our_bid, buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, our_ask, -sell_qty))

        return

    def run(self, state: TradingState):
        conversions = 0
        if state.traderData:
            data = jsonpickle.decode(state.traderData)
        else:
            data = {
                "KELP_mid": [],
            }
        result = {}

        self.log(state)

        if "RAINFOREST_RESIN" in state.order_depths:
            order_depth = state.order_depths["RAINFOREST_RESIN"]
            position = state.position.get("RAINFOREST_RESIN", 0)
            orders: List[Order] = []
            buy_order_volume, sell_order_volume = self.take_best_orders(
                "RAINFOREST_RESIN", position, 10000, 1,
                order_depth, orders
            )
            buy_order_volume, sell_order_volume = self.clear_position_orders(
                "RAINFOREST_RESIN", position, 10000, 0,
                order_depth, orders, buy_order_volume, sell_order_volume
            )
            self.make_market(
                "RAINFOREST_RESIN", position, 10000,
                1, 4, 7,
                order_depth, orders,
                buy_order_volume, sell_order_volume,
                25
            )
            result["RAINFOREST_RESIN"] = orders
        if "KELP" in state.order_depths:
            best_bid, best_ask = max(order_depth.buy_orders.keys()), min(order_depth.sell_orders.keys())
            mid = (best_bid + best_ask) / 2
            data["KELP_mid"].append(mid)
            if len(data["KELP_mid"]) > 3:
                mean = statistics.mean(data["KELP_mid"][-3:])
                std = statistics.stdev(data["KELP_mid"][-3:])
                order_depth = state.order_depths["KELP"]
                position = state.position.get("KELP", 0)
                orders = []
                buy_order_volume, sell_order_volume = self.take_best_orders(
                    "KELP", position, mean, std*0.5,
                    order_depth, orders
                )
                buy_order_volume, sell_order_volume = self.clear_position_orders(
                    "KELP", position, mean, 0,
                    order_depth, orders, buy_order_volume, sell_order_volume
                )
                self.make_market(
                    "KELP", position, mean,
                    1, 2, 3,
                    order_depth, orders,
                    buy_order_volume, sell_order_volume,
                    10
                )
                result["KELP"] = orders

        return result, conversions, jsonpickle.encode(data)

    def log(self, state: TradingState):
        # print executed orders
        for product in ["RAINFOREST_RESIN", "KELP"]:
            for trade in state.own_trades.get(product, []):
                if trade.timestamp == state.timestamp - 100:
                    action = "BUY" if trade.buyer else "SELL"
                    print(f"[Executed] {action} {trade.quantity} {trade.symbol} @ {trade.price}")
        # print current positions
        for product in ["RAINFOREST_RESIN", "KELP"]:
            position = state.position.get(product, 0)
            print(f"{product} position: {position}")
