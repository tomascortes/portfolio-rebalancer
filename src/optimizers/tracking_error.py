"""Tracking error minimization strategy using MILP optimization.

Mathematical Formulation (L1 norm minimization):

    minimize: sum(e_plus[i] + e_minus[i])

    subject to:
        x[i] * p[i] - w[i] * V = e_plus[i] - e_minus[i]   (deviation balance)
        sum(x[i] * p[i]) <= V                              (budget constraint)
        x[i] >= 0, integer                                 (whole shares, no shorting)
        e_plus[i], e_minus[i] >= 0                         (slack variables)

    where:
        x[i]     = shares of asset i (decision variable)
        p[i]     = price per share of asset i
        w[i]     = target weight for asset i
        V        = total portfolio value
        e_plus   = positive deviation (under-allocated)
        e_minus  = negative deviation (over-allocated)

This strategy minimizes the total absolute deviation from target allocations,
producing a portfolio that tracks the target weights as closely as possible
while respecting the whole-share constraint.
"""

from decimal import Decimal

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class TrackingErrorStrategy(RebalanceStrategy):
    """Minimize tracking error (L1 deviation from target) using MILP."""

    def calculate_orders(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
        price_lookup: dict[str, Decimal] | None = None,
    ) -> list[RebalanceOrder]:
        price_lookup = price_lookup or {}

        if total_value == 0:
            return []

        # Collect all symbols and their prices
        symbols = list(target_allocation.keys())
        n = len(symbols)

        prices = []
        current_holdings = []
        target_values = []

        for symbol in symbols:
            if symbol in holdings:
                price = float(holdings[symbol].current_price)
                current_qty = holdings[symbol].quantity
            elif symbol in price_lookup:
                price = float(price_lookup[symbol])
                current_qty = 0
            else:
                raise ValueError(
                    f"Symbol {symbol} in target allocation but not in holdings "
                    f"and no price provided in price_lookup"
                )

            prices.append(price)
            current_holdings.append(current_qty)
            target_values.append(float(target_allocation[symbol]) * float(total_value))

        prices = np.array(prices)
        current_holdings = np.array(current_holdings)
        target_values = np.array(target_values)
        V = float(total_value)

        # Variables: [x_1, ..., x_n, e_plus_1, ..., e_plus_n, e_minus_1, ..., e_minus_n]
        # x = shares to hold (integer)
        # e_plus = positive deviation slack (continuous)
        # e_minus = negative deviation slack (continuous)

        # Objective: minimize sum(e_plus) + sum(e_minus)
        c = np.zeros(3 * n)
        c[n : 2 * n] = 1.0  # e_plus coefficients
        c[2 * n : 3 * n] = 1.0  # e_minus coefficients

        # Constraint 1: Deviation balance
        # x[i] * p[i] - target[i] = e_plus[i] - e_minus[i]
        # => p[i] * x[i] - e_plus[i] + e_minus[i] = target[i]
        A_eq = np.zeros((n, 3 * n))
        for i in range(n):
            A_eq[i, i] = prices[i]  # x[i] coefficient
            A_eq[i, n + i] = -1.0  # e_plus[i] coefficient
            A_eq[i, 2 * n + i] = 1.0  # e_minus[i] coefficient

        deviation_constraint = LinearConstraint(A_eq, target_values, target_values)

        # Constraint 2: Budget constraint
        # sum(x[i] * p[i]) <= V
        A_budget = np.zeros((1, 3 * n))
        A_budget[0, :n] = prices
        budget_constraint = LinearConstraint(A_budget, -np.inf, V)

        # Bounds: x >= 0, e_plus >= 0, e_minus >= 0
        lower = np.zeros(3 * n)
        upper = np.full(3 * n, np.inf)
        bounds = Bounds(lower, upper)

        # Integrality: x is integer, e_plus and e_minus are continuous
        integrality = np.zeros(3 * n, dtype=int)
        integrality[:n] = 1  # Only x variables are integers

        result = milp(
            c=c,
            constraints=[deviation_constraint, budget_constraint],
            integrality=integrality,
            bounds=bounds,
        )

        if not result.success:
            # Fall back to simple strategy if optimization fails
            from .simple import SimpleRebalanceStrategy

            return SimpleRebalanceStrategy().calculate_orders(
                holdings, target_allocation, total_value, price_lookup
            )

        # Extract solution
        x_optimal = np.round(result.x[:n]).astype(int)

        # Build orders
        orders: list[RebalanceOrder] = []

        for i, symbol in enumerate(symbols):
            target_shares = int(x_optimal[i])
            current_qty = int(current_holdings[i])
            delta = target_shares - current_qty

            if delta == 0:
                continue

            price = Decimal(str(prices[i]))
            shares = abs(delta)
            actual_amount = Decimal(shares) * price

            # Calculate target and deviation for the order
            target_dollar_value = Decimal(str(target_values[i]))
            actual_dollar_value = Decimal(target_shares) * price
            deviation = abs(target_dollar_value - actual_dollar_value)

            action = "BUY" if delta > 0 else "SELL"

            orders.append(
                RebalanceOrder(
                    action=action,  # type: ignore[arg-type]
                    symbol=symbol,
                    shares=shares,
                    dollar_amount=actual_amount,
                    target_dollars=abs(target_dollar_value - Decimal(current_qty) * price),
                    deviation_dollars=deviation,
                )
            )

        # Sell holdings not in target allocation
        for symbol, stock in holdings.items():
            if symbol not in target_allocation and stock.quantity > 0:
                orders.append(
                    RebalanceOrder(
                        action="SELL",
                        symbol=symbol,
                        shares=stock.quantity,
                        dollar_amount=stock.market_value,
                        target_dollars=stock.market_value,
                        deviation_dollars=Decimal("0"),
                    )
                )

        return orders
