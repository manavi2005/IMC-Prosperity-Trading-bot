# -*- coding: utf-8 -*-
"""Round2_LP.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1E-zc7882BWJm4ExoOjDWqN1IgIDut-dT
"""

# -*- coding: utf-8 -*-
"""Graded Trading Bot Code

This implementation includes:
- Resin strategy (fixed fair value)
- Kelp strategy (with volume-weighted fair value calculation and historical tracking)
- Squid Ink strategy with mean reversion enhancements:
    • Computes a moving average and standard deviation from recent Squid Ink fair values.
    • Uses a z–score to adjust utility so that trades favor short-term reversion.
- Execution realism adjustments via execution_slippage and transaction_cost.
- Adjustable risk_coefficient and maximum trade volume.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import List, Tuple
import jsonpickle
import math

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

class Trader:
    def __init__(self,
                 execution_slippage: float = 0.2,    # Lower slippage to encourage trading
                 transaction_cost: float = 0.2,        # Lower transaction cost penalty
                 risk_coefficient: float = 0.05,       # Lower risk penalty
                 max_trade_volume: int = 10,           # Increase max trade volume per order
                 reversion_coefficient: float = 0.5     # Coefficient for mean-reversion bonus
                ):
        self.execution_slippage = execution_slippage
        self.transaction_cost = transaction_cost
        self.risk_coefficient = risk_coefficient
        self.max_trade_volume = max_trade_volume
        self.reversion_coefficient = reversion_coefficient

        # Historical data trackers for visualization or computing metrics.
        self.kelp_prices = []        # Stores fair values for KELP.
        self.kelp_vwap = []          # Stores VWAP and volume info for KELP.
        self.squidink_prices = []    # Stores fair values for SQUID_INK.

    # 1) RESIN STRATEGY (Fixed fair value)
    def resin_orders(self, order_depth: OrderDepth, fair_value: int, width: int,
                     position: int, position_limit: int) -> List[Order]:
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0

        # For Resin, we maintain a fixed fair value.
        fair_value = 10000

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if best_ask < fair_value:
                quantity = min(best_ask_amount, position_limit - position)
                if quantity > 0:
                    orders.append(Order("RAINFOREST_RESIN", best_ask, quantity))
                    buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if best_bid > fair_value:
                quantity = min(best_bid_amount, position_limit + position)
                if quantity > 0:
                    orders.append(Order("RAINFOREST_RESIN", best_bid, -quantity))
                    sell_order_volume += quantity

        buy_order_volume, sell_order_volume = self.clear_position_order(
            orders, order_depth, position, position_limit, "RAINFOREST_RESIN",
            buy_order_volume, sell_order_volume, fair_value, width=1
        )

        # Fill remaining capacity with passive orders.
        buy_quantity = position_limit - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order("RAINFOREST_RESIN", fair_value - 1, buy_quantity))
        sell_quantity = position_limit + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order("RAINFOREST_RESIN", fair_value + 1, -sell_quantity))

        return orders

    # 2) KELP STRATEGY
    def kelp_fair_value(self, order_depth: OrderDepth, method="volume_weighted") -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return 2000  # fallback value

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        if method == "volume_weighted":
            total_sell_volume = sum(abs(vol) for vol in order_depth.sell_orders.values())
            total_buy_volume = sum(abs(vol) for vol in order_depth.buy_orders.values())
            if total_sell_volume == 0 or total_buy_volume == 0:
                return 2000
            weighted_sell_price = sum(price * abs(vol) for price, vol in order_depth.sell_orders.items()) / total_sell_volume
            weighted_buy_price  = sum(price * abs(vol) for price, vol in order_depth.buy_orders.items()) / total_buy_volume
            return (weighted_sell_price + weighted_buy_price) / 2
        return (best_ask + best_bid) / 2

    def kelp_orders(self, order_depth: OrderDepth, timespan: int, width: float,
                    take_width: float, position: int, position_limit: int) -> List[Order]:
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0

        if not order_depth.sell_orders or not order_depth.buy_orders:
            return orders

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        fair_value = self.kelp_fair_value(order_depth, method="volume_weighted")

        volume = -order_depth.sell_orders[best_ask] + order_depth.buy_orders[best_bid]
        vwap = (best_bid * (-order_depth.sell_orders[best_ask]) +
                best_ask * order_depth.buy_orders[best_bid]) / volume

        # Track fair value and VWAP.
        self.kelp_vwap.append({"vol": volume, "vwap": vwap})
        self.kelp_prices.append(fair_value)

        # Keep history within the defined time window.
        if len(self.kelp_vwap) > timespan:
            self.kelp_vwap.pop(0)
        if len(self.kelp_prices) > timespan:
            self.kelp_prices.pop(0)

        if best_ask <= fair_value - take_width:
            ask_amount = -order_depth.sell_orders[best_ask]
            if ask_amount <= 20:
                quantity = min(ask_amount, position_limit - position)
                if quantity > 0:
                    orders.append(Order("KELP", best_ask, quantity))
                    buy_order_volume += quantity

        if best_bid >= fair_value + take_width:
            bid_amount = order_depth.buy_orders[best_bid]
            if bid_amount <= 20:
                quantity = min(bid_amount, position_limit + position)
                if quantity > 0:
                    orders.append(Order("KELP", best_bid, -quantity))
                    sell_order_volume += quantity

        buy_order_volume, sell_order_volume = self.clear_position_order(
            orders, order_depth, position, position_limit, "KELP",
            buy_order_volume, sell_order_volume, fair_value, width=2
        )

        # Passive order pricing.
        aaf = [price for price in order_depth.sell_orders.keys() if price > fair_value + 1]
        bbf = [price for price in order_depth.buy_orders.keys() if price < fair_value - 1]
        passive_sell_price = min(aaf) if aaf else fair_value + 2
        passive_buy_price = max(bbf) if bbf else fair_value - 2

        buy_quantity = position_limit - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order("KELP", passive_buy_price + 1, buy_quantity))
        sell_quantity = position_limit + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order("KELP", passive_sell_price - 1, -sell_quantity))
        return orders

    # 3) SQUID INK STRATEGY WITH MEAN REVERSION
    def squidink_fair_value(self, order_depth: OrderDepth, method="volume_weighted") -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return 2000
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        if method == "volume_weighted":
            total_sell_volume = sum(abs(vol) for vol in order_depth.sell_orders.values())
            total_buy_volume = sum(abs(vol) for vol in order_depth.buy_orders.values())
            if total_sell_volume == 0 or total_buy_volume == 0:
                return 2000
            weighted_sell_price = sum(price * abs(vol) for price, vol in order_depth.sell_orders.items()) / total_sell_volume
            weighted_buy_price  = sum(price * abs(vol) for price, vol in order_depth.buy_orders.items()) / total_buy_volume
            return (weighted_sell_price + weighted_buy_price) / 2
        return (best_ask + best_bid) / 2

    def compute_swing_metric(self, window: int = 10) -> Tuple[float, float]:
        """Compute the moving average and standard deviation for the recent Squid Ink fair values."""
        recent = self.squidink_prices[-window:] if len(self.squidink_prices) >= window else self.squidink_prices
        if not recent:
            return 0, 0
        avg = sum(recent) / len(recent)
        variance = sum((x - avg) ** 2 for x in recent) / len(recent)
        std = math.sqrt(variance)
        return avg, std

    def mid_price(self, order_depth: OrderDepth, fallback: float) -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return fallback
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        return (best_ask + best_bid) / 2

    def optimize_conversion_arbitrage(self, prices: dict, position_limits: dict) -> Tuple[dict, float]:
        """
        A math‐only implementation that “solves” the LP:

            maximize sum(q_i * adv_i)  subject to q_i in [-limit, limit]

        where the decision variables q_i correspond to each product in
        [CROISSANT, JAM, DJEMBE, PICNIC_BASKET1, PICNIC_BASKET2].

        The synthetic fair values for baskets are computed as:

            synthetic_b1 = 6 * CROISSANT + 3 * JAM + 1 * DJEMBE
            synthetic_b2 = 4 * CROISSANT + 2 * JAM

        This function returns a decision dictionary and the total profit.
        """
        items = ["CROISSANT", "JAM", "DJEMBE", "PICNIC_BASKET1", "PICNIC_BASKET2"]
        fv_c = prices["CROISSANT"]
        fv_j = prices["JAM"]
        fv_d = prices["DJEMBE"]
        synthetic_b1 = 6 * fv_c + 3 * fv_j + 1 * fv_d
        synthetic_b2 = 4 * fv_c + 2 * fv_j

        # Construct the advantage vector.
        adv = [
            prices["CROISSANT"] - fv_c,      # Typically ~0 unless mispriced.
            prices["JAM"] - fv_j,
            prices["DJEMBE"] - fv_d,
            prices["PICNIC_BASKET1"] - synthetic_b1,
            prices["PICNIC_BASKET2"] - synthetic_b2,
        ]

        decision = {}
        total_profit = 0
        for i, item in enumerate(items):
            limit = position_limits[item]
            if adv[i] > 0:
                decision[item] = limit
                total_profit += adv[i] * limit
            elif adv[i] < 0:
                decision[item] = -limit
                total_profit += adv[i] * (-limit)
            else:
                decision[item] = 0
        return decision, total_profit


    # Helper: Decompose LP Decision into Executable Orders
    def decompose_lp_conversion_orders(self, state: TradingState, prices: dict, lp_decision: dict) -> List[Order]:
        """
        Using the LP conversion decision and current positions, compute the orders needed to adjust positions.
        For each product, if the LP target differs from the current position, generate an order at the
        best available price.
        """
        conversion_orders = []
        for product, target_net in lp_decision.items():
            current_position = state.position.get(product, 0)
            order_volume = target_net - current_position
            # Only trade if the adjustment is nonzero.
            if abs(order_volume) < 1:  # ignore negligible differences
                continue

            # Determine order price using the order depth if available.
            if product in state.order_depths:
                od = state.order_depths[product]
                if order_volume > 0 and od.sell_orders:
                    price = min(od.sell_orders.keys())
                elif order_volume < 0 and od.buy_orders:
                    price = max(od.buy_orders.keys())
                else:
                    price = prices.get(product, 1000)  # fallback price
            else:
                price = prices.get(product, 1000)
            conversion_orders.append(Order(product, price, int(order_volume)))
        return conversion_orders

    def squidink_utility_orders(self, order_depth: OrderDepth, position: int, position_limit: int,
                                fair_value_base: float = 2000, candidate_range: int = 2) -> List[Order]:
        orders: List[Order] = []
        fair_value = self.squidink_fair_value(order_depth, method="volume_weighted")
        if fair_value == 0:
            fair_value = fair_value_base

        # Record the raw fair value.
        self.squidink_prices.append(fair_value)
        # Compute recent average and volatility.
        avg, std = self.compute_swing_metric(window=10)
        z = (fair_value - avg) / std if std > 0 else 0  # z-score of current price

        candidate_prices = [int(fair_value + offset) for offset in range(-candidate_range, candidate_range + 1)]
        best_buy_price = None
        best_buy_utility = float("-inf")
        best_sell_price = None
        best_sell_utility = float("-inf")

        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None

        for price in candidate_prices:
            if price < fair_value:
                distance = best_ask - price if best_ask is not None else candidate_range
                exec_prob = max(0, 1 - (distance / candidate_range))
                profit = fair_value - price - self.execution_slippage - self.transaction_cost
                penalty = self.risk_coefficient * abs(position + 1)
                base_utility = (profit - penalty) * exec_prob
                # If oversold (negative z), add bonus proportional to its magnitude.
                bonus = self.reversion_coefficient * (-z) if z < 0 else 0
                utility = base_utility + bonus
                if utility > best_buy_utility:
                    best_buy_utility = utility
                    best_buy_price = price

            if price > fair_value:
                distance = price - best_bid if best_bid is not None else candidate_range
                exec_prob = max(0, 1 - (distance / candidate_range))
                profit = price - fair_value - self.execution_slippage - self.transaction_cost
                penalty = self.risk_coefficient * abs(position - 1)
                base_utility = (profit - penalty) * exec_prob
                # If overbought (positive z), add bonus proportional to z.
                bonus = self.reversion_coefficient * z if z > 0 else 0
                utility = base_utility + bonus
                if utility > best_sell_utility:
                    best_sell_utility = utility
                    best_sell_price = price

        buy_volume = min(self.max_trade_volume, position_limit - position)
        sell_volume = min(self.max_trade_volume, position_limit + position)
        if best_buy_price is not None and buy_volume > 0:
            orders.append(Order("SQUID_INK", best_buy_price, buy_volume))
        if best_sell_price is not None and sell_volume > 0:
            orders.append(Order("SQUID_INK", best_sell_price, -sell_volume))
        return orders

    def croissant_fair_value(self, order_depth: OrderDepth) -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return 4300
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        return (best_ask + best_bid) / 2

    def jam_fair_value(self, order_depth: OrderDepth) -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return 6600
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        return (best_ask + best_bid) / 2

    def djembe_fair_value(self, order_depth: OrderDepth) -> float:
        if not order_depth.sell_orders or not order_depth.buy_orders:
            return 13400
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        return (best_ask + best_bid) / 2

    def croissant_orders(self, order_depth: OrderDepth, position: int, position_limit: int) -> List[Order]:
        orders: List[Order] = []
        fair_value = self.croissant_fair_value(order_depth)
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            available = -order_depth.sell_orders[best_ask]
            if best_ask < fair_value:
                quantity = min(available, position_limit - position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("CROISSANT", best_ask, quantity))
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            available = order_depth.buy_orders[best_bid]
            if best_bid > fair_value:
                quantity = min(available, position_limit + position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("CROISSANT", best_bid, -quantity))
        return orders

    def jam_orders(self, order_depth: OrderDepth,
                   position: int, position_limit: int) -> List[Order]:
        orders: List[Order] = []
        fair_value = self.jam_fair_value(order_depth)
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            available = -order_depth.sell_orders[best_ask]
            if best_ask < fair_value:
                quantity = min(available, position_limit - position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("JAM", best_ask, quantity))
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            available = order_depth.buy_orders[best_bid]
            if best_bid > fair_value:
                quantity = min(available, position_limit + position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("JAM", best_bid, -quantity))
        return orders

    def djembe_orders(self, order_depth: OrderDepth,
                      position: int, position_limit: int) -> List[Order]:
        orders: List[Order] = []
        fair_value = self.djembe_fair_value(order_depth)
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            available = -order_depth.sell_orders[best_ask]
            if best_ask < fair_value:
                quantity = min(available, position_limit - position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("DJEMBE", best_ask, quantity))
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            available = order_depth.buy_orders[best_bid]
            if best_bid > fair_value:
                quantity = min(available, position_limit + position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("DJEMBE", best_bid, -quantity))
        return orders

    def basket1_orders(self, order_depths: dict, position: int, position_limit: int) -> List[Order]:
        """
        For PICNIC_BASKET1, which is composed of:
          6 CROISSANTS, 3 JAM, 1 DJEMBE.
        We compute synthetic fair value from component order depths.
        """
        croissant_depth = order_depths["CROISSANT"]
        jam_depth = order_depths["JAM"]
        djembe_depth = order_depths["DJEMBE"]
        basket_depth = order_depths["PICNIC_BASKET1"]

        synthetic_fv = (6 * self.croissant_fair_value(croissant_depth) +
                        3 * self.jam_fair_value(jam_depth) +
                        1 * self.djembe_fair_value(djembe_depth))
        orders = []
        if basket_depth.sell_orders:
            best_ask = min(basket_depth.sell_orders.keys())
            available = -basket_depth.sell_orders[best_ask]
            if best_ask < synthetic_fv:
                quantity = min(available, position_limit - position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("PICNIC_BASKET1", best_ask, quantity))
        if basket_depth.buy_orders:
            best_bid = max(basket_depth.buy_orders.keys())
            available = basket_depth.buy_orders[best_bid]
            if best_bid > synthetic_fv:
                quantity = min(available, position_limit + position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("PICNIC_BASKET1", best_bid, -quantity))
        return orders

    def basket2_orders(self, order_depths: dict, position: int, position_limit: int) -> List[Order]:
        """
        For PICNIC_BASKET2, composed of:
          4 CROISSANTS, 2 JAM.
        """
        croissant_depth = order_depths["CROISSANT"]
        jam_depth = order_depths["JAM"]
        basket_depth = order_depths["PICNIC_BASKET2"]

        synthetic_fv = 4 * self.croissant_fair_value(croissant_depth) + 2 * self.jam_fair_value(jam_depth)
        orders = []
        if basket_depth.sell_orders:
            best_ask = min(basket_depth.sell_orders.keys())
            available = -basket_depth.sell_orders[best_ask]
            if best_ask < synthetic_fv:
                quantity = min(available, position_limit - position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("PICNIC_BASKET2", best_ask, quantity))
        if basket_depth.buy_orders:
            best_bid = max(basket_depth.buy_orders.keys())
            available = basket_depth.buy_orders[best_bid]
            if best_bid > synthetic_fv:
                quantity = min(available, position_limit + position, self.max_trade_volume)
                if quantity > 0:
                    orders.append(Order("PICNIC_BASKET2", best_bid, -quantity))
        return orders

    # 4) CLEAR POSITION HELPER (Shared Across Products)
    def clear_position_order(self, orders: List[Order], order_depth: OrderDepth,
                             position: int, position_limit: int, product: str,
                             buy_order_volume: int, sell_order_volume: int,
                             fair_value: float, width: int) -> (int, int):
        position_after = position + buy_order_volume - sell_order_volume
        fair_bid = math.floor(fair_value)
        fair_ask = math.ceil(fair_value)
        buy_capacity  = position_limit - (position + buy_order_volume)
        sell_capacity = position_limit + (position - sell_order_volume)
        if position_after > 0:
            if fair_ask in order_depth.buy_orders:
                clear_qty = min(order_depth.buy_orders[fair_ask], position_after)
                qty_to_sell = min(sell_capacity, clear_qty)
                if qty_to_sell > 0:
                    orders.append(Order(product, fair_ask, -abs(qty_to_sell)))
                    sell_order_volume += abs(qty_to_sell)
        elif position_after < 0:
            if fair_bid in order_depth.sell_orders:
                clear_qty = min(abs(order_depth.sell_orders[fair_bid]), abs(position_after))
                qty_to_buy = min(buy_capacity, clear_qty)
                if qty_to_buy > 0:
                    orders.append(Order(product, fair_bid, qty_to_buy))
                    buy_order_volume += abs(qty_to_buy)
        return buy_order_volume, sell_order_volume

    # 5) MAIN RUN (ENTRY POINT)
    def run(self, state: TradingState):
        result = {}

        resin_position_limit = 50
        kelp_position_limit = 50
        squidink_position_limit = 50

        kelp_make_width = 3.5
        kelp_take_width = 1
        timespan = 10  # number of historical steps to store

        if "RAINFOREST_RESIN" in state.order_depths:
            resin_position = state.position.get("RAINFOREST_RESIN", 0)
            resin_orders = self.resin_orders(
                state.order_depths["RAINFOREST_RESIN"],
                fair_value=10000,  # fixed fair value for Resin
                width=2,
                position=resin_position,
                position_limit=resin_position_limit
            )
            result["RAINFOREST_RESIN"] = resin_orders

        if "KELP" in state.order_depths:
            kelp_position = state.position.get("KELP", 0)
            kelp_orders = self.kelp_orders(
                state.order_depths["KELP"],
                timespan,
                kelp_make_width,
                kelp_take_width,
                kelp_position,
                kelp_position_limit
            )
            result["KELP"] = kelp_orders

        if "SQUID_INK" in state.order_depths:
            squidink_position = state.position.get("SQUID_INK", 0)
            squidink_orders = self.squidink_utility_orders(
                state.order_depths["SQUID_INK"],
                position=squidink_position,
                position_limit=squidink_position_limit,
                fair_value_base=2000,
                candidate_range=2
            )
            result["SQUID_INK"] = squidink_orders

        pos_limits = {
            "CROISSANT": 250,
            "JAM": 350,
            "DJEMBE": 60,
            "PICNIC_BASKET1": 60,
            "PICNIC_BASKET2": 100,
        }

        if "CROISSANT" in state.order_depths:
            pos = state.position.get("CROISSANT", 0)
            result["CROISSANT"] = self.croissant_orders(state.order_depths["CROISSANT"], pos, pos_limits["CROISSANT"])

        if "JAM" in state.order_depths:
            pos = state.position.get("JAM", 0)
            result["JAM"] = self.jam_orders(state.order_depths["JAM"], pos, pos_limits["JAM"])

        if "DJEMBE" in state.order_depths:
            pos = state.position.get("DJEMBE", 0)
            result["DJEMBE"] = self.djembe_orders(state.order_depths["DJEMBE"], pos, pos_limits["DJEMBE"])

        if all(p in state.order_depths for p in ["CROISSANT", "DJEMBE", "JAM", "PICNIC_BASKET1"]):
            basket_position = state.position.get("PICNIC_BASKET1", 0)
            result["PICNIC_BASKET1"] = self.basket1_orders(
                state.order_depths,
                basket_position,
                pos_limits["PICNIC_BASKET1"]
            )

        if all(p in state.order_depths for p in ["CROISSANT", "DJEMBE", "JAM", "PICNIC_BASKET2"]):
            basket_position = state.position.get("PICNIC_BASKET2", 0)
            result["PICNIC_BASKET2"] = self.basket2_orders(
                state.order_depths,
                basket_position,
                pos_limits["PICNIC_BASKET2"]
            )

        # Build a dictionary of current prices using mid-prices or fallbacks.
        prices = {}
        for prod, fallback in [("CROISSANT", 4300), ("JAM", 6600), ("DJEMBE", 13400)]:
            if prod in state.order_depths:
                prices[prod] = self.mid_price(state.order_depths[prod], fallback)
            else:
                prices[prod] = fallback
        # For baskets, if available use order depths; else use synthetic conversion.
        if "PICNIC_BASKET1" in state.order_depths:
            prices["PICNIC_BASKET1"] = self.mid_price(
                state.order_depths["PICNIC_BASKET1"],
                6 * prices["CROISSANT"] + 3 * prices["JAM"] + prices["DJEMBE"]
            )
        else:
            prices["PICNIC_BASKET1"] = 6 * prices["CROISSANT"] + 3 * prices["JAM"] + prices["DJEMBE"]

        if "PICNIC_BASKET2" in state.order_depths:
            prices["PICNIC_BASKET2"] = self.mid_price(
                state.order_depths["PICNIC_BASKET2"],
                4 * prices["CROISSANT"] + 2 * prices["JAM"]
            )
        else:
            prices["PICNIC_BASKET2"] = 4 * prices["CROISSANT"] + 2 * prices["JAM"]

        # Run the LP conversion arbitrage optimizer.
        lp_decision, lp_profit = self.optimize_conversion_arbitrage(prices, pos_limits)
        # Decompose LP decision into executable orders:
        conversion_orders = self.decompose_lp_conversion_orders(state, prices, lp_decision)
        # Insert conversion orders into the result dict so that each product key gets its order.
        for order in conversion_orders:
            symbol = order.symbol
            if symbol in result:
                result[symbol].append(order)
            else:
                result[symbol] = [order]

        traderData = jsonpickle.encode({
            "kelp_prices": self.kelp_prices,
            "kelp_vwap": self.kelp_vwap,
            "squidink_prices": self.squidink_prices
        })
        conversions = 1

        if plt is not None:
            self.plot_history(self.kelp_prices, self.kelp_vwap)

        return result, conversions, traderData