"""Simple floor-division rebalancing strategy."""

from decimal import Decimal

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class SimpleRebalanceStrategy(RebalanceStrategy):
    """Simple rebalancing using floor division to calculate whole shares.

    This strategy calculates the dollar difference between current and target
    allocations, then uses floor division to determine the number of whole
    shares to trade.
    """

    def calculate_orders(
        self,
        holdings: dict[str, Stock],
        target_allocation: dict[str, Decimal],
        total_value: Decimal,
        price_lookup: dict[str, Decimal] | None = None,
    ) -> list[RebalanceOrder]:
        price_lookup = price_lookup or {}
        orders: list[RebalanceOrder] = []

        if total_value == 0:
            return []

        # Step 1: Process target allocation symbols
        for symbol, target_pct in target_allocation.items():
            target_value = total_value * target_pct

            # Get current value (0 if not held)
            if symbol in holdings:
                current_value = holdings[symbol].market_value
                price = holdings[symbol].current_price
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

            orders.append(
                RebalanceOrder(
                    action=action,  # type: ignore[arg-type]
                    symbol=symbol,
                    shares=shares,
                    dollar_amount=actual_amount,
                    target_dollars=target_amount,
                    deviation_dollars=deviation,
                )
            )

        # Step 2: Sell holdings not in target allocation
        for symbol, stock in holdings.items():
            if symbol not in target_allocation and stock.quantity > 0:
                orders.append(
                    RebalanceOrder(
                        action="SELL",
                        symbol=symbol,
                        shares=stock.quantity,
                        dollar_amount=stock.market_value,
                        target_dollars=stock.market_value,  # Selling all = no deviation
                        deviation_dollars=Decimal("0"),
                    )
                )

        return orders
