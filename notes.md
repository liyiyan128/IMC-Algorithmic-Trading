# IMC Prosperity

## 101

1. **Objective**: Develop a Python `Trader` class to trade algorithmically on the "Island Exchange" against bots, maximizing SeaShells. Competitors submit code that processes market data and generates orders.

2. **Key Components**:
   - **`Trader` Class**: Must implement a `run` method accepting a `TradingState` and returning orders, conversions, and persistent `traderData`.
   - **`TradingState`**: Contains:
     - **Order Depths**: Bots' outstanding buy/sell orders per product (`OrderDepth` class).
     - **Trades**: Recent trades by the algorithm (`own_trades`) and others (`market_trades`).
     - **Positions**: Current holdings per product, subject to **position limits** (absolute max long/short).
     - **Observations**: Data for conversions (e.g., tariffs, transport fees).

3. **Order Execution**:
   - Orders matching bots' quotes execute immediately. Unmatched portions become quotes for bots to trade against; unmatched orders cancel after one iteration.
   - Orders exceeding position limits are rejected.

4. **Strategy Considerations**:
   - **Acceptable Price Logic**: Example strategy buys if best ask < internal "fair price" and sells if best bid > fair price.
   - **State Persistence**: Use `traderData` (string) to serialize/deserialize state between iterations (e.g., with `jsonpickle`).
   - **Conversions**: Optional requests to convert positions, factoring in tariffs and transport costs.

5. **Technical Constraints**:
   - **Libraries**: Limited to pandas, NumPy, math, etc. (see Appendix C).
   - **Timeout**: `run` must execute in **<900ms** per iteration.
   - **Debugging**: Logs include print statements from the algorithm.

6. **Resources**:
   - Sample data (CSV files) for new products.
   - Example `Trader` code and `datamodel.py` (Appendix A/B).

**Action Steps for Participants**:
1. Analyze sample data to model price dynamics.
2. Implement `run` method to process `TradingState`, calculate signals, and generate orders.
3. Manage positions within limits and use `traderData` for multi-iteration strategies.
4. Test locally with provided data models, then upload to the platform (note submission UUID for support).

**Example Logic**:
```python
def run(self, state: TradingState):
    result = {}
    for product in state.order_depths:
        # Calculate acceptable_price based on strategy (e.g., mid-price, EMA)
        best_ask = min(state.order_depths[product].sell_orders) if sell_orders else None
        best_bid = max(state.order_depths[product].buy_orders) if buy_orders else None
        acceptable_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 10
        
        # Place orders
        orders = []
        if best_ask < acceptable_price:
            orders.append(Order(product, best_ask, -best_ask_qty))  # Buy
        if best_bid > acceptable_price:
            orders.append(Order(product, best_bid, best_bid_qty))  # Sell
        result[product] = orders
    return result, 0, traderData  # No conversions
``` 
