"""Abstract base class for rebalancing strategies."""

from abc import ABC, abstractmethod
from decimal import Decimal

from ..models import Stock, RebalanceOrder


class RebalanceStrategy(ABC):
    """Abstract base class for portfolio rebalancing strategies."""

    @abstractmethod
    def calculate_orders(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
        price_lookup: dict[str, Decimal] | None = None,
    ) -> list[RebalanceOrder]:
        """Calculate rebalance orders for the given portfolio state.

        Args:
            holdings: Current stock holdings by symbol.
            target_allocation: Target allocation percentages by symbol (must sum to 1).
            total_value: Total portfolio value.
            price_lookup: Prices for symbols not in holdings.

        Returns:
            List of RebalanceOrder objects representing trades to execute.
        """
        pass
