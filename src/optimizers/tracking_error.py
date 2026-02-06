"""
Tracking error minimization strategy using MILP optimization (L1 norm).

The objective is to track a target portfolio allocation as closely as possible
in dollar terms, subject to whole-share and budget constraints.

Mathematical formulation:

Let:
    x[i] = number of shares of asset i (decision variable)
    p[i] = price per share of asset i
    w[i] = target portfolio weight of asset i
    V    = total portfolio value
    T[i] = w[i] * V = target dollar allocation for asset i

Decision variables:
    x[i]      >= 0, integer   (whole shares, no shorting)
    e_plus[i] >= 0            (positive deviation: under-allocation)
    e_minus[i]>= 0            (negative deviation: over-allocation)

Objective:
    minimize  sum_i (e_plus[i] + e_minus[i])

Subject to:
    p[i] * x[i] - T[i] = e_plus[i] - e_minus[i]   (tracking error balance)
    sum_i (p[i] * x[i]) <= V                      (budget constraint)

This formulation minimizes the total absolute deviation between the actual
dollar allocation and the target dollar allocation for each asset, producing
a portfolio that closely tracks the desired weights while respecting the
whole-share constraint.
"""


from decimal import Decimal

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class TrackingErrorStrategy(RebalanceStrategy):
    """Minimize tracking error (L1 deviation from target) using MILP."""

    def _build_objective_coefficients(self, n: int) -> np.ndarray:
        """Build objective: minimize sum(e_plus) + sum(e_minus)."""
        c = np.zeros(3 * n)
        c[n:] = 1.0
        return c

    def _build_deviation_balance_matrix(
        self, n: int, prices: np.ndarray
    ) -> np.ndarray:
        """Build matrix for: p[i]*x[i] - e_plus[i] + e_minus[i] = target[i]."""
        A = np.zeros((n, 3 * n))
        for i in range(n):
            A[i, i] = prices[i]
            A[i, n + i] = -1.0
            A[i, 2 * n + i] = 1.0
        return A

    def _build_budget_constraint_matrix(
        self, n: int, prices: np.ndarray
    ) -> np.ndarray:
        """Build matrix for: sum(p[i]*x[i]) <= V."""
        A = np.zeros((1, 3 * n))
        A[0, :n] = prices
        return A

    def _build_integrality_constraints(self, n: int) -> np.ndarray:
        """Only share counts (x) are integers; deviations are continuous."""
        integrality = np.zeros(3 * n, dtype=int)
        integrality[:n] = 1
        return integrality

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

        result = milp(
            c=self._build_objective_coefficients(n),
            constraints=[
                LinearConstraint(
                    self._build_deviation_balance_matrix(n, prices),
                    target_values,
                    target_values,
                ),
                LinearConstraint(
                    self._build_budget_constraint_matrix(n, prices),
                    -np.inf,
                    V,
                ),
            ],
            integrality=self._build_integrality_constraints(n),
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
