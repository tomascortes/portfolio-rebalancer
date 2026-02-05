"""Tests for rebalancing optimization strategies."""

import pytest
from decimal import Decimal

from src.models import Stock, RebalanceOrder
from src.portfolio import Portfolio
from src.optimizers import (
    SimpleRebalanceStrategy,
    TrackingErrorStrategy,
    TradeMinimizationStrategy,
)


class TestSimpleRebalanceStrategy:
    def test_basic_rebalance(self):
        strategy = SimpleRebalanceStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 27, Decimal("185")),
            "META": Stock("META", 8, Decimal("580")),
        }
        target = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        order_by_symbol = {o.symbol: o for o in orders}
        assert "AAPL" in order_by_symbol
        assert order_by_symbol["AAPL"].action == "BUY"
        assert order_by_symbol["AAPL"].shares == 4

        assert "META" in order_by_symbol
        assert order_by_symbol["META"].action == "SELL"
        assert order_by_symbol["META"].shares == 1

    def test_whole_shares_only(self):
        strategy = SimpleRebalanceStrategy()
        holdings = {"AAPL": Stock("AAPL", 10, Decimal("100"))}
        target = {"AAPL": Decimal("0.9"), "META": Decimal("0.1")}
        total_value = holdings["AAPL"].market_value

        orders = strategy.calculate_orders(
            holdings, target, total_value, {"META": Decimal("580")}
        )

        # META target is $100, but price is $580, so no shares can be bought
        meta_orders = [o for o in orders if o.symbol == "META"]
        assert len(meta_orders) == 0

    def test_empty_portfolio(self):
        strategy = SimpleRebalanceStrategy()
        orders = strategy.calculate_orders({}, {"AAPL": Decimal("1.0")}, Decimal("0"))
        assert orders == []


class TestTrackingErrorStrategy:
    def test_basic_rebalance(self):
        strategy = TrackingErrorStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 27, Decimal("185")),
            "META": Stock("META", 8, Decimal("580")),
        }
        target = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        # Verify orders are valid
        for order in orders:
            assert order.shares > 0
            assert order.action in ("BUY", "SELL")

    def test_whole_shares_constraint(self):
        strategy = TrackingErrorStrategy()
        holdings = {"AAPL": Stock("AAPL", 10, Decimal("100"))}
        target = {"AAPL": Decimal("0.7"), "META": Decimal("0.3")}
        total_value = holdings["AAPL"].market_value

        orders = strategy.calculate_orders(
            holdings, target, total_value, {"META": Decimal("50")}
        )

        for order in orders:
            assert isinstance(order.shares, int)
            assert order.shares == int(order.shares)

    def test_budget_constraint(self):
        strategy = TrackingErrorStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 10, Decimal("100")),
            "META": Stock("META", 10, Decimal("100")),
        }
        target = {"AAPL": Decimal("0.5"), "META": Decimal("0.5")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        # Calculate resulting portfolio value
        resulting_holdings = {
            "AAPL": holdings["AAPL"].quantity,
            "META": holdings["META"].quantity,
        }
        for order in orders:
            if order.action == "BUY":
                resulting_holdings[order.symbol] += order.shares
            else:
                resulting_holdings[order.symbol] -= order.shares

        resulting_value = (
            resulting_holdings["AAPL"] * 100 + resulting_holdings["META"] * 100
        )
        assert resulting_value <= float(total_value)

    def test_minimizes_deviation_vs_simple(self):
        strategy_tracking = TrackingErrorStrategy()
        strategy_simple = SimpleRebalanceStrategy()

        # Use a scenario where tracking error strategy should do better
        holdings = {
            "AAPL": Stock("AAPL", 5, Decimal("200")),
            "META": Stock("META", 5, Decimal("200")),
        }
        target = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        total_value = sum(s.market_value for s in holdings.values())

        orders_tracking = strategy_tracking.calculate_orders(
            holdings, target, total_value
        )
        orders_simple = strategy_simple.calculate_orders(holdings, target, total_value)

        # Calculate total deviation for each strategy
        def calc_final_deviation(orders, holdings, target, total_value, prices):
            final_holdings = {s: holdings[s].quantity for s in holdings}
            for order in orders:
                if order.action == "BUY":
                    final_holdings[order.symbol] = final_holdings.get(order.symbol, 0) + order.shares
                else:
                    final_holdings[order.symbol] = final_holdings.get(order.symbol, 0) - order.shares

            total_dev = Decimal("0")
            for symbol, target_pct in target.items():
                actual_value = Decimal(final_holdings.get(symbol, 0)) * prices[symbol]
                target_value = target_pct * total_value
                total_dev += abs(actual_value - target_value)
            return total_dev

        prices = {s: holdings[s].current_price for s in holdings}
        dev_tracking = calc_final_deviation(
            orders_tracking, holdings, target, total_value, prices
        )
        dev_simple = calc_final_deviation(
            orders_simple, holdings, target, total_value, prices
        )

        # Tracking error strategy should have equal or lower deviation
        assert dev_tracking <= dev_simple

    def test_empty_portfolio(self):
        strategy = TrackingErrorStrategy()
        orders = strategy.calculate_orders({}, {"AAPL": Decimal("1.0")}, Decimal("0"))
        assert orders == []

    def test_sells_unlisted_holdings(self):
        strategy = TrackingErrorStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 10, Decimal("100")),
            "GOOG": Stock("GOOG", 5, Decimal("200")),
        }
        target = {"AAPL": Decimal("1.0")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        goog_orders = [o for o in orders if o.symbol == "GOOG"]
        assert len(goog_orders) == 1
        assert goog_orders[0].action == "SELL"
        assert goog_orders[0].shares == 5


class TestTradeMinimizationStrategy:
    def test_basic_rebalance(self):
        strategy = TradeMinimizationStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 27, Decimal("185")),
            "META": Stock("META", 8, Decimal("580")),
        }
        target = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        # Verify orders are valid
        for order in orders:
            assert order.shares > 0
            assert order.action in ("BUY", "SELL")

    def test_tolerance_parameter(self):
        # With a large tolerance, no trades should be needed
        strategy = TradeMinimizationStrategy(tolerance=Decimal("0.5"))
        holdings = {
            "AAPL": Stock("AAPL", 6, Decimal("100")),
            "META": Stock("META", 4, Decimal("100")),
        }
        target = {"AAPL": Decimal("0.5"), "META": Decimal("0.5")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        # With 50% tolerance, current 60/40 split should be acceptable
        assert len(orders) == 0

    def test_minimizes_trades_vs_simple(self):
        strategy_trade = TradeMinimizationStrategy(tolerance=Decimal("0.05"))
        strategy_simple = SimpleRebalanceStrategy()

        holdings = {
            "AAPL": Stock("AAPL", 10, Decimal("100")),
            "META": Stock("META", 10, Decimal("100")),
        }
        target = {"AAPL": Decimal("0.52"), "META": Decimal("0.48")}
        total_value = sum(s.market_value for s in holdings.values())

        orders_trade = strategy_trade.calculate_orders(holdings, target, total_value)
        orders_simple = strategy_simple.calculate_orders(holdings, target, total_value)

        total_shares_trade = sum(o.shares for o in orders_trade)
        total_shares_simple = sum(o.shares for o in orders_simple)

        # Trade minimization should trade equal or fewer shares
        assert total_shares_trade <= total_shares_simple

    def test_whole_shares_constraint(self):
        strategy = TradeMinimizationStrategy()
        holdings = {"AAPL": Stock("AAPL", 10, Decimal("100"))}
        target = {"AAPL": Decimal("0.7"), "META": Decimal("0.3")}
        total_value = holdings["AAPL"].market_value

        orders = strategy.calculate_orders(
            holdings, target, total_value, {"META": Decimal("50")}
        )

        for order in orders:
            assert isinstance(order.shares, int)
            assert order.shares == int(order.shares)

    def test_stays_within_tolerance(self):
        tolerance = Decimal("0.02")
        strategy = TradeMinimizationStrategy(tolerance=tolerance)

        holdings = {
            "AAPL": Stock("AAPL", 10, Decimal("100")),
            "META": Stock("META", 10, Decimal("100")),
        }
        target = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        # Calculate resulting allocations
        final_holdings = {"AAPL": 10, "META": 10}
        for order in orders:
            if order.action == "BUY":
                final_holdings[order.symbol] += order.shares
            else:
                final_holdings[order.symbol] -= order.shares

        final_value = sum(
            final_holdings[s] * float(holdings[s].current_price) for s in final_holdings
        )

        for symbol, target_pct in target.items():
            actual_pct = (
                final_holdings[symbol] * float(holdings[symbol].current_price)
            ) / final_value
            assert abs(actual_pct - float(target_pct)) <= float(tolerance) + 0.001

    def test_empty_portfolio(self):
        strategy = TradeMinimizationStrategy()
        orders = strategy.calculate_orders({}, {"AAPL": Decimal("1.0")}, Decimal("0"))
        assert orders == []

    def test_sells_unlisted_holdings(self):
        strategy = TradeMinimizationStrategy()
        holdings = {
            "AAPL": Stock("AAPL", 10, Decimal("100")),
            "GOOG": Stock("GOOG", 5, Decimal("200")),
        }
        target = {"AAPL": Decimal("1.0")}
        total_value = sum(s.market_value for s in holdings.values())

        orders = strategy.calculate_orders(holdings, target, total_value)

        goog_orders = [o for o in orders if o.symbol == "GOOG"]
        assert len(goog_orders) == 1
        assert goog_orders[0].action == "SELL"
        assert goog_orders[0].shares == 5


class TestPortfolioStrategyIntegration:
    def test_simple_strategy_via_portfolio(self):
        p = Portfolio()
        p.add_stock(Stock("AAPL", 27, Decimal("185")))
        p.add_stock(Stock("META", 8, Decimal("580")))
        p.set_target_allocation({"AAPL": Decimal("0.6"), "META": Decimal("0.4")})

        orders = p.rebalance(strategy="simple")
        assert isinstance(orders, list)

    def test_tracking_error_strategy_via_portfolio(self):
        p = Portfolio()
        p.add_stock(Stock("AAPL", 27, Decimal("185")))
        p.add_stock(Stock("META", 8, Decimal("580")))
        p.set_target_allocation({"AAPL": Decimal("0.6"), "META": Decimal("0.4")})

        orders = p.rebalance(strategy="tracking_error")
        assert isinstance(orders, list)

    def test_trade_minimization_strategy_via_portfolio(self):
        p = Portfolio()
        p.add_stock(Stock("AAPL", 27, Decimal("185")))
        p.add_stock(Stock("META", 8, Decimal("580")))
        p.set_target_allocation({"AAPL": Decimal("0.6"), "META": Decimal("0.4")})

        orders = p.rebalance(strategy="trade_minimization")
        assert isinstance(orders, list)

    def test_invalid_strategy_raises(self):
        p = Portfolio()
        p.add_stock(Stock("AAPL", 10, Decimal("100")))
        p.set_target_allocation({"AAPL": Decimal("1.0")})

        with pytest.raises(ValueError, match="Unknown strategy"):
            p.rebalance(strategy="nonexistent")  # type: ignore

    def test_default_strategy_is_simple(self):
        p = Portfolio()
        p.add_stock(Stock("AAPL", 27, Decimal("185")))
        p.add_stock(Stock("META", 8, Decimal("580")))
        p.set_target_allocation({"AAPL": Decimal("0.6"), "META": Decimal("0.4")})

        # Default should work and be equivalent to simple
        orders_default = p.rebalance()
        orders_simple = p.rebalance(strategy="simple")

        # Same number of orders
        assert len(orders_default) == len(orders_simple)
