"""Trade minimization strategy using MILP optimization.

Mathematical Formulation:

    minimize: sum(t_plus[i] + t_minus[i])

    subject to:
        x[i] - h[i] = t_plus[i] - t_minus[i]              (trade balance)
        (w[i] - tol) * V <= x[i] * p[i] <= (w[i] + tol) * V   (tolerance band)
        sum(x[i] * p[i]) <= V                              (budget constraint)
        x[i], t_plus[i], t_minus[i] >= 0, integer          (whole shares)

    where:
        x[i]     = shares of asset i to hold (decision variable)
        h[i]     = current holdings of asset i
        p[i]     = price per share of asset i
        w[i]     = target weight for asset i
        V        = total portfolio value
        tol      = tolerance (default 2%)
        t_plus   = shares to buy
        t_minus  = shares to sell

This strategy minimizes the total number of shares traded while keeping
allocations within a tolerance band of the target weights.
"""

from decimal import Decimal

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class TradeMinimizationStrategy(RebalanceStrategy):
    """Minimize number of trades while staying within tolerance band."""

    def __init__(self, tolerance: Decimal = Decimal("0.02")):
        """Initialize with tolerance band.

        Args:
            tolerance: Allowed deviation from target weight (default 2%).
        """
        self.tolerance = tolerance

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
        target_weights = []

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
            target_weights.append(float(target_allocation[symbol]))

        prices = np.array(prices)
        current_holdings = np.array(current_holdings)
        target_weights = np.array(target_weights)
        V = float(total_value)
        tol = float(self.tolerance)

        # Variables: [x_1, ..., x_n, t_plus_1, ..., t_plus_n, t_minus_1, ..., t_minus_n]
        # x = shares to hold (integer)
        # t_plus = shares to buy (integer)
        # t_minus = shares to sell (integer)

        # Objective: minimize sum(t_plus) + sum(t_minus)
        c = np.zeros(3 * n)
        c[n : 2 * n] = 1.0  # t_plus coefficients
        c[2 * n : 3 * n] = 1.0  # t_minus coefficients

        # Constraint 1: Trade balance
        # x[i] - h[i] = t_plus[i] - t_minus[i]
        # => x[i] - t_plus[i] + t_minus[i] = h[i]
        A_trade = np.zeros((n, 3 * n))
        for i in range(n):
            A_trade[i, i] = 1.0  # x[i] coefficient
            A_trade[i, n + i] = -1.0  # t_plus[i] coefficient
            A_trade[i, 2 * n + i] = 1.0  # t_minus[i] coefficient

        trade_constraint = LinearConstraint(A_trade, current_holdings, current_holdings)

        # Constraint 2: Tolerance band (lower bound)
        # (w[i] - tol) * V <= x[i] * p[i]
        # => x[i] * p[i] >= (w[i] - tol) * V
        A_lower = np.zeros((n, 3 * n))
        for i in range(n):
            A_lower[i, i] = prices[i]

        lower_bounds = np.maximum((target_weights - tol) * V, 0)
        tolerance_lower = LinearConstraint(A_lower, lower_bounds, np.full(n, np.inf))

        # Constraint 3: Tolerance band (upper bound)
        # x[i] * p[i] <= (w[i] + tol) * V
        A_upper = np.zeros((n, 3 * n))
        for i in range(n):
            A_upper[i, i] = prices[i]

        upper_bounds = (target_weights + tol) * V
        tolerance_upper = LinearConstraint(A_upper, -np.full(n, np.inf), upper_bounds)

        # Constraint 4: Budget constraint
        # sum(x[i] * p[i]) <= V
        A_budget = np.zeros((1, 3 * n))
        A_budget[0, :n] = prices
        budget_constraint = LinearConstraint(A_budget, -np.inf, V)

        # Bounds: x >= 0, t_plus >= 0, t_minus >= 0
        lower = np.zeros(3 * n)
        upper = np.full(3 * n, np.inf)
        bounds = Bounds(lower, upper)

        # Integrality: all variables are integers
        integrality = np.ones(3 * n, dtype=int)

        result = milp(
            c=c,
            constraints=[trade_constraint, tolerance_lower, tolerance_upper, budget_constraint],
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
            target_dollar_value = Decimal(str(target_weights[i])) * total_value
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
