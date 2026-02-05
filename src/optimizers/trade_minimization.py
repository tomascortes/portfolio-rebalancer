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

        symbols = list(target_allocation.keys())
        n = len(symbols)

        prices, current_holdings = self._collect_symbol_data(
            symbols, holdings, price_lookup
        )
        target_weights = np.array([float(target_allocation[s]) for s in symbols])
        V = float(total_value)
        tol = float(self.tolerance)

        # Variables: [x_1..x_n, t_plus_1..t_plus_n, t_minus_1..t_minus_n]
        c = np.zeros(3 * n)
        c[n:] = 1.0  # minimize sum(t_plus) + sum(t_minus)

        # Trade balance: x[i] - t_plus[i] + t_minus[i] = h[i]
        A_trade = np.zeros((n, 3 * n))
        for i in range(n):
            A_trade[i, i] = 1.0
            A_trade[i, n + i] = -1.0
            A_trade[i, 2 * n + i] = 1.0

        # Tolerance band: (w[i] - tol) * V <= x[i] * p[i] <= (w[i] + tol) * V
        A_tolerance = np.zeros((n, 3 * n))
        np.fill_diagonal(A_tolerance, prices)

        A_budget = np.zeros((1, 3 * n))
        A_budget[0, :n] = prices

        result = milp(
            c=c,
            constraints=[
                LinearConstraint(A_trade, current_holdings, current_holdings),
                LinearConstraint(
                    A_tolerance,
                    np.maximum((target_weights - tol) * V, 0),
                    (target_weights + tol) * V,
                ),
                LinearConstraint(A_budget, -np.inf, V),
            ],
            integrality=np.ones(3 * n, dtype=int),
            bounds=Bounds(np.zeros(3 * n), np.full(3 * n, np.inf)),
        )

        if not result.success:
            from .simple import SimpleRebalanceStrategy

            return SimpleRebalanceStrategy().calculate_orders(
                holdings, target_allocation, total_value, price_lookup
            )

        optimal_shares = np.round(result.x[:n]).astype(int)
        orders = self._orders_from_solution(
            symbols, prices, current_holdings, optimal_shares,
            target_allocation, total_value,
        )
        return orders + self._liquidation_orders(holdings, target_allocation)
