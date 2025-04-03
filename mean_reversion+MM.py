import numpy as np
import statistics
import jsonpickle
from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order, Trade


class Trader:
    def __init__(self):
        self.traderData = jsonpickle.encode({
            "RAINFOREST_RESIN_mid": [],
            "KELP_mid": [],
            "KELP_spreads": [],
        })

    def run(self, state: TradingState):
        conversions = 0
        if state.traderData:
            data = jsonpickle.decode(state.traderData)
        else:
            data = {
                "RAINFOREST_RESIN_mid": [],
                "KELP_mid": [],
                "KELP_spreads": [],
                }

        result = {}
        for product in ["RAINFOREST_RESIN", "KELP"]:
            if product in state.order_depths:
                order_depth = state.order_depths[product]
                best_bid, best_ask = self.get_best_prices(order_depth)
                mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else None
                data[f"{product}_mid"].append(mid_price) if mid_price else None
                position = state.position.get(product, 0)
                if product == "KELP":
                    spread = best_ask - best_bid if best_bid and best_ask else None
                    data["KELP_spreads"].append(spread) if spread else None
                # Generate orders
                if product == "RAINFOREST_RESIN":
                    orders = self.process_resin(order_depth, position, data)
                else:
                    orders = self.process_kelp(order_depth, position, data)
                result[product] = orders

        # Close positions if time is running out
        self.close_positions(state, data, result)

        # Logging
        self.log(state, data)

        new_trader_data = jsonpickle.encode(data)
        return result, conversions, new_trader_data

    def get_best_prices(self, order_depth: OrderDepth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask

    def get_farthest_price(self, order_depth: OrderDepth):
        far_bid = min(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        far_ask = max(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return far_bid, far_ask

    def process_resin(self, order_depth: OrderDepth, position: int, data: dict) -> List[Order]:
        orders = []
        position_limit = 50
        best_bid, best_ask = self.get_best_prices(order_depth)
        mid_price = (best_bid + best_ask) / 2
        if best_bid is None or best_ask is None:
            return []
        lo = 9999
        hi = 10001
        if position == 0:
            if mid_price <= lo:
                print("Opening long position")
                orders.append(Order("RAINFOREST_RESIN", lo, 20))
            elif mid_price >= hi:
                print("Opening short position")
                orders.append(Order("RAINFOREST_RESIN", hi, -20))
        elif position > 0:
            if mid_price >= hi:
                print("Closing long position")
                price = max(int(mid_price+0.5), hi)
                orders.append(Order("RAINFOREST_RESIN", price, -position))
            elif mid_price < lo:
                size = min(10, position_limit - position)
                price = min((int(mid_price), best_ask, lo))
                print("Increasing long position")
                orders.append(Order("RAINFOREST_RESIN", price, size)) if size > 0 else None
        elif position < 0:
            if mid_price <= lo:
                print("Closing short position")
                price = min(int(mid_price), lo)
                orders.append(Order("RAINFOREST_RESIN", price, -position))
            elif mid_price >= hi:
                size = min(10, position_limit + position)
                price = max((int(mid_price+0.5), best_bid, hi))
                print("Increasing short position")
                orders.append(Order("RAINFOREST_RESIN", price, -size)) if size > 0 else None
        return orders

    def process_kelp(self, order_depth: OrderDepth, position: int, data: dict) -> List[Order]:
        WINDOW = 5
        INVENTORY_LIMIT = 40
        orders = []
        best_bid, best_ask = self.get_best_prices(order_depth)
        if best_bid is None or best_ask is None:
            return []
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        data["KELP_mid"].append(mid_price)
        data["KELP_spreads"].append(spread)
        if len(data["KELP_mid"]) < WINDOW:
            return []

        # Volume imbalance
        bid_volume = sum(order_depth.buy_orders.values())
        ask_volume = sum(order_depth.sell_orders.values())
        # vol_imb = (ask_volume - bid_volume) / (ask_volume + bid_volume)

        # Rolling mean and std
        mid = np.array(data["KELP_mid"][-WINDOW:])
        mean = np.mean(mid)
        std = np.std(mid)

        position_limit = 50
        position_factor = position / position_limit * 2

        base_spread = std
        our_bid = mid_price - base_spread - position_factor
        our_ask = mid_price + base_spread + position_factor
        our_bid = int(our_bid)
        our_ask = int(our_ask)
        our_spread = our_ask - our_bid
        # Make market
        buy_size = min(position_limit-position, int(ask_volume/2))
        sell_size = min(position_limit+position, int(bid_volume/2))
        orders.append(Order("KELP", our_bid, buy_size)) if position < INVENTORY_LIMIT else None
        orders.append(Order("KELP", our_ask, -sell_size)) if -position < INVENTORY_LIMIT else None

        return orders

    def close_positions(self, state: TradingState, data: dict, result: Dict[str, List[Order]]) -> None:
        LIQUIDATION_WINDOW = 200
        FINAL_TIMESTAMP = 199900
        TIME_LEFT = FINAL_TIMESTAMP - state.timestamp
        if TIME_LEFT > LIQUIDATION_WINDOW:
            return

        for product in ["RAINFOREST_RESIN", "KELP"]:
            orders = []
            position = state.position.get(product, 0)
            if position > 0:
                for price in state.order_depths[product].buy_orders.keys():
                    size = min(position, state.order_depths[product].buy_orders[price])
                    orders.append(Order(product, price, -size))
                    position -= size
                    if position <= 0:
                        break
            elif position < 0:
                for price in state.order_depths[product].sell_orders.keys():
                    size = min(-position, -state.order_depths[product].sell_orders[price])
                    orders.append(Order(product, price, size))
                    position += size
                    if position >= 0:
                        break
            result[product] = orders

    def log(self, state, data):
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
