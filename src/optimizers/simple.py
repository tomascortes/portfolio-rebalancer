from decimal import Decimal
from typing import Literal

from ..models import Stock, RebalanceOrder
from .base import RebalanceStrategy


class SimpleRebalanceStrategy(RebalanceStrategy):

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

        orders: list[RebalanceOrder] = []
        for symbol, target_pct in target_allocation.items():
            order = self._create_rebalance_order(
                symbol, target_pct, total_value, holdings, price_lookup
            )
            if order:
                orders.append(order)

        return orders + self._liquidation_orders(holdings, target_allocation)

    def _get_price_and_value(
        self,
        symbol: str,
        holdings: dict[str, Stock],
        price_lookup: dict[str, Decimal],
    ) -> tuple[Decimal, Decimal]:
        if symbol in holdings:
            return holdings[symbol].current_price, holdings[symbol].market_value
        if symbol in price_lookup:
            return price_lookup[symbol], Decimal("0")
        raise ValueError(
            f"Symbol {symbol} in target allocation but not in holdings "
            f"and no price provided in price_lookup"
        )

    def _create_rebalance_order(
        self,
        symbol: str,
        target_pct: Decimal,
        total_value: Decimal,
        holdings: dict[str, Stock],
        price_lookup: dict[str, Decimal],
    ) -> RebalanceOrder | None:
        target_value = total_value * target_pct
        price, current_value = self._get_price_and_value(symbol, holdings, price_lookup)
        delta_dollars = target_value - current_value

        if delta_dollars == 0:
            return None

        shares = int(abs(delta_dollars) // price)
        if shares == 0:
            return None

        actual_amount = Decimal(shares) * price
        action: Literal["BUY", "SELL"] = "BUY" if delta_dollars > 0 else "SELL"

        return RebalanceOrder(
            action=action,
            symbol=symbol,
            shares=shares,
            dollar_amount=actual_amount,
            target_dollars=abs(delta_dollars),
            deviation_dollars=abs(delta_dollars) - actual_amount,
        )
