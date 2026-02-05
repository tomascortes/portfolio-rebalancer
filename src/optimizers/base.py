"""Abstract base class for rebalancing strategies."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Literal

import numpy as np

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

    def _collect_symbol_data(
        self,
        symbols: list[str],
        holdings: dict[str, Stock],
        price_lookup: dict[str, Decimal],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extract prices and current quantities as numpy arrays, ordered by symbols."""
        prices, quantities = [], []

        for symbol in symbols:
            if symbol in holdings:
                prices.append(float(holdings[symbol].current_price))
                quantities.append(holdings[symbol].quantity)
            elif symbol in price_lookup:
                prices.append(float(price_lookup[symbol]))
                quantities.append(0)
            else:
                raise ValueError(
                    f"Symbol {symbol} in target allocation but not in holdings "
                    f"and no price provided in price_lookup"
                )

        return np.array(prices), np.array(quantities)

    def _orders_from_solution(
        self,
        symbols: list[str],
        prices: np.ndarray,
        current_holdings: np.ndarray,
        optimal_shares: np.ndarray,
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
    ) -> list[RebalanceOrder]:
        """Convert an optimal share vector into a list of RebalanceOrders."""
        orders: list[RebalanceOrder] = []

        for i, symbol in enumerate(symbols):
            target_qty = int(optimal_shares[i])
            current_qty = int(current_holdings[i])
            delta = target_qty - current_qty

            if delta == 0:
                continue

            price = Decimal(str(prices[i]))
            target_value = target_allocation[symbol] * total_value
            action: Literal["BUY", "SELL"] = "BUY" if delta > 0 else "SELL"

            orders.append(
                RebalanceOrder(
                    action=action,
                    symbol=symbol,
                    shares=abs(delta),
                    dollar_amount=Decimal(abs(delta)) * price,
                    target_dollars=abs(target_value - Decimal(current_qty) * price),
                    deviation_dollars=abs(target_value - Decimal(target_qty) * price),
                )
            )

        return orders

    def _liquidation_orders(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
    ) -> list[RebalanceOrder]:
        """Sell orders for any holdings not in the target allocation."""
        return [
            RebalanceOrder(
                action="SELL",
                symbol=symbol,
                shares=stock.quantity,
                dollar_amount=stock.market_value,
                target_dollars=stock.market_value,
                deviation_dollars=Decimal("0"),
            )
            for symbol, stock in holdings.items()
            if symbol not in target_allocation and stock.quantity > 0
        ]
