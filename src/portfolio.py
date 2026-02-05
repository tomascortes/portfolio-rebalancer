from decimal import Decimal
from typing import Optional

from .models import Stock, RebalanceOrder


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

    def rebalance(self, price_lookup: Optional[dict[str, Decimal]] = None) -> list[RebalanceOrder]:
        """Calculate orders needed to rebalance portfolio to target allocation."""
        if not self.target_allocation:
            raise ValueError("No target allocation set. Call set_target_allocation() first.")

        price_lookup = price_lookup or {}
        orders: list[RebalanceOrder] = []
        total = self.total_value()

        if total == 0:
            return []  # Can't rebalance an empty portfolio

        # Step 1: Process target allocation symbols
        for symbol, target_pct in self.target_allocation.items():
            target_value = total * target_pct

            # Get current value (0 if not held)
            if symbol in self.holdings:
                current_value = self.holdings[symbol].market_value
                price = self.holdings[symbol].current_price
            elif symbol in price_lookup:
                current_value = Decimal("0")
                price = price_lookup[symbol]
            else:
                raise ValueError(
                    f"Symbol {symbol} in target allocation but not in holdings "
                    f"and no price provided in price_lookup"
                )

            delta_dollars = target_value - current_value

            if delta_dollars == 0:
                continue  # Already at target

            shares = int(abs(delta_dollars) // price)

            if shares == 0:
                continue  # Delta too small to trade even 1 share

            actual_amount = Decimal(shares) * price
            target_amount = abs(delta_dollars)
            deviation = target_amount - actual_amount

            action: str = "BUY" if delta_dollars > 0 else "SELL"

            orders.append(RebalanceOrder(
                action=action,  # type: ignore[arg-type]
                symbol=symbol,
                shares=shares,
                dollar_amount=actual_amount,
                target_dollars=target_amount,
                deviation_dollars=deviation
            ))

        # Step 2: Sell holdings not in target allocation
        for symbol, stock in self.holdings.items():
            if symbol not in self.target_allocation and stock.quantity > 0:
                orders.append(RebalanceOrder(
                    action="SELL",
                    symbol=symbol,
                    shares=stock.quantity,
                    dollar_amount=stock.market_value,
                    target_dollars=stock.market_value,  # Selling all = no deviation
                    deviation_dollars=Decimal("0")
                ))

        return orders

    @classmethod
    def from_url(cls, url: str, name: str) -> "Portfolio":
        raise NotImplementedError("Web loading not yet implemented.")

    def __repr__(self) -> str:
        return (
            f"Portfolio(holdings={list(self.holdings.keys())}, "
            f"total_value={self.total_value()}, "
            f"target_allocation={self.target_allocation})"
        )
