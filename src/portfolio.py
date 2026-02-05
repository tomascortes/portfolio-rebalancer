from decimal import Decimal
from typing import Literal, Optional

from .models import Stock, RebalanceOrder
from .optimizers import (
    SimpleRebalanceStrategy,
    TrackingErrorStrategy,
    TradeMinimizationStrategy,
)

StrategyName = Literal["simple", "tracking_error", "trade_minimization"]


class Portfolio:
    """A stock portfolio with target allocation and rebalancing capability."""

    ALLOCATION_SUM_TOLERANCE = Decimal("0.0001")

    def __init__(self) -> None:
        self.holdings: dict[str, Stock] = {}
        self.target_allocation: dict[str, Decimal] = {}

    def add_stock(self, stock: Stock) -> None:
        self.holdings[stock.symbol] = stock

    def remove_stock(self, symbol: str) -> Optional[Stock]:
        return self.holdings.pop(symbol, None)

    def set_target_allocation(self, allocation: dict[str, Decimal]) -> None:
        for symbol, pct in allocation.items():
            if pct < 0 or pct > 1:
                raise ValueError(
                    f"Allocation for {symbol} must be between 0 and 1, got {pct}"
                )

        total = sum(allocation.values())
        if abs(total - Decimal("1")) > self.ALLOCATION_SUM_TOLERANCE:
            raise ValueError(
                f"Allocations must sum to 1.0, got {total}"
            )

        self.target_allocation = allocation.copy()

    def total_value(self) -> Decimal:
        return sum(
            (stock.market_value for stock in self.holdings.values()),
            start=Decimal("0")
        )

    def current_allocation(self) -> dict[str, Decimal]:
        total = self.total_value()
        if total == 0:
            return {}

        return {
            symbol: stock.market_value / total
            for symbol, stock in self.holdings.items()
        }

    def rebalance(
        self,
        price_lookup: Optional[dict[str, Decimal]] = None,
        strategy: StrategyName = "simple",
    ) -> list[RebalanceOrder]:
        """Calculate orders needed to rebalance portfolio to target allocation.

        Args:
            price_lookup: Prices for symbols not in holdings.
            strategy: Rebalancing strategy to use:
                - "simple": Floor division (default, fast)
                - "tracking_error": Minimize deviation from target allocation (L1 norm)
                - "trade_minimization": Minimize number of shares traded

        Returns:
            List of RebalanceOrder objects.
        """
        if not self.target_allocation:
            raise ValueError("No target allocation set. Call set_target_allocation() first.")

        total = self.total_value()
        if total == 0:
            return []  # Can't rebalance an empty portfolio

        strategies = {
            "simple": SimpleRebalanceStrategy,
            "tracking_error": TrackingErrorStrategy,
            "trade_minimization": TradeMinimizationStrategy,
        }

        strategy_cls = strategies.get(strategy)
        if strategy_cls is None:
            raise ValueError(f"Unknown strategy: {strategy}")

        strategy_instance = strategy_cls()
        return strategy_instance.calculate_orders(
            self.holdings, self.target_allocation, total, price_lookup
        )

    @classmethod
    def from_url(cls, url: str, name: str = "") -> "Portfolio":
        """Create a Portfolio with target allocation loaded from a URL.

        Args:
            url: URL to scrape allocation from (e.g., https://fintual.cl/risky-norris).
            name: Optional portfolio name (currently unused).

        Returns:
            Portfolio instance with target allocation set from the scraped data.
        """
        from .loaders import load_from_url

        allocation = load_from_url(url)
        portfolio = cls()
        portfolio.set_target_allocation(allocation)
        return portfolio

    def __repr__(self) -> str:
        return (
            f"Portfolio(holdings={list(self.holdings.keys())}, "
            f"total_value={self.total_value()}, "
            f"target_allocation={self.target_allocation})"
        )
