"""
Trade minimization strategy using MILP optimization.

The objective is to minimize the number of distinct assets traded (i.e., assets
with any buy or sell activity) while ensuring the final portfolio allocation
stays within a tolerance band around the target weights.

Mathematical formulation:

Let:
    x[i] = final number of shares of asset i (decision variable)
    h[i] = current holdings of asset i
    p[i] = price per share of asset i
    w[i] = target portfolio weight of asset i
    V    = total portfolio value
    tol  = tolerance around target weights
    M    = big-M constant (upper bound on possible traded shares)

Decision variables:
    x[i]       >= 0, integer   (final shares to hold)
    t_plus[i]  >= 0, integer   (shares bought)
    t_minus[i] >= 0, integer   (shares sold)
    y[i]       in {0, 1}       (1 if asset i is traded, 0 otherwise)

Objective:
    minimize  sum_i y[i]

Subject to:
    x[i] = h[i] + t_plus[i] - t_minus[i]              (trade balance)
    t_plus[i] + t_minus[i] <= M * y[i]                (trade indicator linking)
    (w[i] - tol) * V <= x[i] * p[i] <= (w[i] + tol) * V   (value-based tolerance band)
    sum_i (x[i] * p[i]) <= V                          (budget constraint)

This formulation minimizes the number of assets that require trading, regardless
of trade size, while ensuring the resulting portfolio remains close to the
target allocation in dollar terms.
"""

from decimal import Decimal

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class TradeMinimizationStrategy(RebalanceStrategy):
    """Minimize number of distinct trades while staying within tolerance band."""

    def __init__(self, tolerance: Decimal = Decimal("0.02")):
        self.tolerance = tolerance

    def calculate_orders(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
        price_lookup: dict[str, Decimal] | None = None,
        extra_cash: Decimal = Decimal("0"),
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
        budget = V + float(extra_cash)
        tol = float(self.tolerance)

        M = self._compute_big_m(budget, prices)
        num_vars = 4 * n

        result = milp(
            c=self._build_objective(n, prices, budget),
            constraints=[
                self._build_trade_balance_constraint(n, current_holdings),
                self._build_indicator_constraint(n, M),
                self._build_tolerance_constraint(n, prices, target_weights, tol, V),
                self._build_budget_constraint(n, prices, budget),
            ],
            integrality=np.ones(num_vars, dtype=int),
            bounds=self._build_variable_bounds(num_vars, n),
        )

        if not result.success:
            return self._fallback_to_simple_strategy(
                holdings, target_allocation, total_value, price_lookup
            )

        optimal_shares = np.round(result.x[:n]).astype(int)
        orders = self._orders_from_solution(
            symbols, prices, current_holdings, optimal_shares,
            target_allocation, total_value,
        )
        return orders + self._liquidation_orders(holdings, target_allocation)

    def _build_objective(self, n: int, prices: np.ndarray, budget: float) -> np.ndarray:
        c = np.zeros(4 * n)
        c[3 * n:] = 1.0
        epsilon = 0.5 / budget if budget > 0 else 0
        c[:n] = -epsilon * prices
        return c

    def _compute_big_m(self, V: float, prices: np.ndarray) -> float:
        min_price = max(prices.min(), 0.01)
        return 2 * V / min_price

    def _build_trade_balance_constraint(
        self, n: int, current_holdings: np.ndarray
    ) -> LinearConstraint:
        A = np.zeros((n, 4 * n))
        idx = np.arange(n)
        A[idx, idx] = 1.0
        A[idx, n + idx] = -1.0
        A[idx, 2 * n + idx] = 1.0
        return LinearConstraint(A, current_holdings, current_holdings)

    def _build_indicator_constraint(self, n: int, M: float) -> LinearConstraint:
        A = np.zeros((n, 4 * n))
        idx = np.arange(n)
        A[idx, n + idx] = 1.0
        A[idx, 2 * n + idx] = 1.0
        A[idx, 3 * n + idx] = -M
        return LinearConstraint(A, -np.inf, np.zeros(n))

    def _build_tolerance_constraint(
        self, n: int, prices: np.ndarray, target_weights: np.ndarray, tol: float, V: float
    ) -> LinearConstraint:
        A = np.zeros((n, 4 * n))
        np.fill_diagonal(A, prices)
        lower = np.maximum((target_weights - tol) * V, 0)
        upper = (target_weights + tol) * V
        return LinearConstraint(A, lower, upper)

    def _build_budget_constraint(
        self, n: int, prices: np.ndarray, V: float
    ) -> LinearConstraint:
        A = np.zeros((1, 4 * n))
        A[0, :n] = prices
        return LinearConstraint(A, -np.inf, V)

    def _build_variable_bounds(self, num_vars: int, n: int) -> Bounds:
        lower = np.zeros(num_vars)
        upper = np.full(num_vars, np.inf)
        upper[3 * n:] = 1.0
        return Bounds(lower, upper)

    def _fallback_to_simple_strategy(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
        price_lookup: dict[str, Decimal] | None,
    ) -> list[RebalanceOrder]:
        from .simple import SimpleRebalanceStrategy
        return SimpleRebalanceStrategy().calculate_orders(
            holdings, target_allocation, total_value, price_lookup
        )
