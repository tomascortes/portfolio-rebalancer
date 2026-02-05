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

        symbols = list(target_allocation.keys())
        n = len(symbols)

        prices, current_holdings = self._collect_symbol_data(
            symbols, holdings, price_lookup
        )
        target_values = np.array(
            [float(target_allocation[s]) * float(total_value) for s in symbols]
        )
        V = float(total_value)

        # Variables: [x_1..x_n, e_plus_1..e_plus_n, e_minus_1..e_minus_n]
        c = np.zeros(3 * n)
        c[n:] = 1.0  # minimize sum(e_plus) + sum(e_minus)

        # Deviation balance: p[i]*x[i] - e_plus[i] + e_minus[i] = target[i]
        A_eq = np.zeros((n, 3 * n))
        for i in range(n):
            A_eq[i, i] = prices[i]
            A_eq[i, n + i] = -1.0
            A_eq[i, 2 * n + i] = 1.0

        A_budget = np.zeros((1, 3 * n))
        A_budget[0, :n] = prices

        integrality = np.zeros(3 * n, dtype=int)
        integrality[:n] = 1  # only share counts are integers

        result = milp(
            c=c,
            constraints=[
                LinearConstraint(A_eq, target_values, target_values),
                LinearConstraint(A_budget, -np.inf, V),
            ],
            integrality=integrality,
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
