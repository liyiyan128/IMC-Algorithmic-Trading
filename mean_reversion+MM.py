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
        for product in ["RAINFOREST_RESIN"]:
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
        # window = 10
        best_bid, best_ask = self.get_best_prices(order_depth)
        if best_bid is None or best_ask is None:
            return []
        mid_price = (best_bid + best_ask) / 2

        orders = []
        position_limit = 50
        buy_threshold = 9999
        sell_threshold = 10001
        if position > 0:
            if mid_price >= buy_threshold:
                # Close long position
                orders.append(Order("RAINFOREST_RESIN", best_ask, -position))
                print("Closing long position")
        elif position < 0:
            if mid_price < sell_threshold:
                # Close short position
                orders.append(Order("RAINFOREST_RESIN", best_bid, -position))
                print("Closing short position")
        else:
            # Open new position
            if mid_price =< buy_threshold:
                orders.append(Order("RAINFOREST_RESIN", best_bid, position_limit))
                print("Opening long position")
            elif mid_price >= sell_threshold:
                orders.append(Order("RAINFOREST_RESIN", best_ask, -position_limit))
                print("Opening short position")

        return orders

    def process_kelp(self, order_depth: OrderDepth, position: int, data: dict) -> List[Order]:
        # Calculate spread
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else 0
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else 0
        if best_bid == 0 or best_ask == 0:
            return []
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        data["KELP_mid"].append(mid_price)
        data["KELP_spreads"].append(spread)
        if len(data["KELP_mid"]) < 10:
            return []

        # Calculate volatility
        mid = np.array(data["KELP_mid"][-10:])
        returns = np.diff(mid) / mid[:-1]
        vol = np.std(returns)
        vol_adjust = 0.5

        position_limit = 50
        position_adjust = position / position_limit * 5

        spread_adjust = 0.5*vol_adjust*vol**2*position

        our_bid = mid_price - spread_adjust - position_adjust
        our_ask = mid_price + spread_adjust + position_adjust
        our_bid = int(our_bid)
        our_ask = int(our_ask)
        our_spread = our_ask - our_bid

        orders = []
        if our_spread <= 1:
            # The spread is too tight, no orders, close positions
            if position != 0:
                price = best_ask if position > 0 else best_bid
                orders.append(Order("KELP", price, -position))
                print("Spread too tight, closing position")
        else:
            buy_volume = sum(order_depth.buy_orders.values())
            sell_volume = sum(order_depth.sell_orders.values())
            buy_size = min(sell_volume*0.5, position_limit-position)
            sell_size = min(buy_volume*0.5, position_limit+position)
            if buy_size > 0:
                orders.append(Order("KELP", int(our_bid), int(buy_size)))
            if sell_size > 0:
                orders.append(Order("KELP", int(our_ask), -int(sell_size)))

        print(f"[KELP] Mkt Mid: {mid_price}, Mkt Spread: {spread}, Vol: {vol:.2f}")
        print(f"[KELP] Our Bid: {our_bid}, Our Ask: {our_ask}, Our Spread: {our_ask - our_bid}")

        return orders

    def close_positions(self, state: TradingState, data: dict, result: Dict[str, List[Order]]) -> None:
        LIQUIDATION_WINDOW = 300
        FINAL_TIMESTAMP = 200000
        if (FINAL_TIMESTAMP - state.timestamp) > LIQUIDATION_WINDOW:
            return

        for product in state.position:
            position = state.position[product]
            if position == 0:
                continue

            # Get best available prices
            order_depth = state.order_depths.get(product, OrderDepth())
            best_bid, best_ask = self.get_best_prices(order_depth)
            # If no liquidity
            if not best_bid or not best_ask:
                mid_price = statistics.mean(data[f"{product}_mid"][-3:])
                best_bid = int(mid_price - 1)
                best_ask = int(mid_price + 1)

            time_remaining = (FINAL_TIMESTAMP - state.timestamp) / LIQUIDATION_WINDOW
            if time_remaining <= 100:  # market order liquidation
                price = best_ask if position > 0 else best_bid
                orders = [Order(product, int(price), -position)]
            else:  # passive liquidation with price improvement
                step_size = int(max(1, abs(position)//time_remaining))
                if position > 0:
                    # Sell ladder
                    prices = sorted(order_depth.buy_orders.keys(), reverse=True)
                    orders = self.create_ladder_orders(product, position, prices, step_size, sell=True)
                else:
                    # Buy ladder
                    prices = sorted(order_depth.sell_orders.keys())
                    orders = self.create_ladder_orders(product, abs(position), prices, step_size, sell=False)
            result[product] = orders

    def create_ladder_orders(self, product: str, total_qty: int, prices: List[int], step: int, sell: bool) -> List[Order]:
        orders = []
        remaining = total_qty
        for price in prices:
            if remaining <= 0:
                break
            qty = min(remaining, step)
            orders.append(Order(product, int(price), -qty if sell else qty))
            remaining -= qty
        return orders

    def log(self, state, data):
        # print executed orders
        for product in ["RAINFOREST_RESIN", "KELP"]:
            for order in state.own_trades.get(product, []):
                print(f"Executed: {order}")
        # print current positions
        for product in ["RAINFOREST_RESIN", "KELP"]:
            position = state.position.get(product, 0)
            print(f"{product} position: {position}")