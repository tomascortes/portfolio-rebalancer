"""Data models for the portfolio rebalancer."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass
class Stock:
    """Represents a stock holding with current price information."""

    symbol: str
    quantity: int
    current_price: Decimal

    @property
    def market_value(self) -> Decimal:
        return Decimal(self.quantity) * self.current_price

    def update_price(self, price: Decimal) -> None:
        self.current_price = price


@dataclass(frozen=True)
class RebalanceOrder:
    """Represents a rebalance order with deviation tracking."""

    action: Literal["BUY", "SELL"]
    symbol: str
    shares: int
    dollar_amount: Decimal
    target_dollars: Decimal
    deviation_dollars: Decimal

    def __str__(self) -> str:
        return (
            f"{self.action} {self.shares} {self.symbol} "
            f"(${self.dollar_amount:.2f}, target: ${self.target_dollars:.2f}, "
            f"deviation: ${self.deviation_dollars:.2f})"
        )
