import pytest
from decimal import Decimal

from src.models import Stock, RebalanceOrder
from src.portfolio import Portfolio


class TestStock:
    def test_market_value(self):
        stock = Stock("AAPL", 10, Decimal("185.50"))
        assert stock.market_value == Decimal("1855.00")

    def test_market_value_zero_quantity(self):
        stock = Stock("AAPL", 0, Decimal("185.50"))
        assert stock.market_value == Decimal("0")

    def test_update_price(self):
        stock = Stock("AAPL", 10, Decimal("185.50"))
        stock.update_price(Decimal("200.00"))
        assert stock.current_price == Decimal("200.00")
        assert stock.market_value == Decimal("2000.00")


class TestRebalanceOrder:
    def test_str_representation(self):
        order = RebalanceOrder(
            action="BUY",
            symbol="AAPL",
            shares=5,
            dollar_amount=Decimal("925.00"),
            target_dollars=Decimal("1000.00"),
            deviation_dollars=Decimal("75.00")
        )
        assert "BUY" in str(order)
        assert "AAPL" in str(order)
        assert "5" in str(order)


class TestPortfolio:
    def test_add_stock(self):
        portfolio = Portfolio()
        stock = Stock("AAPL", 10, Decimal("185"))
        portfolio.add_stock(stock)
        assert "AAPL" in portfolio.holdings
        assert portfolio.holdings["AAPL"].quantity == 10

    def test_remove_stock(self):
        portfolio = Portfolio()
        stock = Stock("AAPL", 10, Decimal("185"))
        portfolio.add_stock(stock)
        removed = portfolio.remove_stock("AAPL")
        assert removed == stock
        assert "AAPL" not in portfolio.holdings

    def test_remove_nonexistent_stock(self):
        portfolio = Portfolio()
        assert portfolio.remove_stock("AAPL") is None

    def test_total_value(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("185")))
        portfolio.add_stock(Stock("META", 5, Decimal("580")))
        assert portfolio.total_value() == Decimal("4750")

    def test_total_value_empty_portfolio(self):
        portfolio = Portfolio()
        assert portfolio.total_value() == Decimal("0")

    def test_current_allocation(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("100")))
        portfolio.add_stock(Stock("META", 10, Decimal("100")))
        allocation = portfolio.current_allocation()
        assert allocation["AAPL"] == Decimal("0.5")
        assert allocation["META"] == Decimal("0.5")

    def test_current_allocation_empty(self):
        portfolio = Portfolio()
        assert portfolio.current_allocation() == {}


class TestTargetAllocation:
    def test_valid_allocation(self):
        portfolio = Portfolio()
        allocation = {"AAPL": Decimal("0.6"), "META": Decimal("0.4")}
        portfolio.set_target_allocation(allocation)
        assert portfolio.target_allocation == allocation

    def test_allocation_must_sum_to_one(self):
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="sum to 1.0"):
            portfolio.set_target_allocation({
                "AAPL": Decimal("0.5"),
                "META": Decimal("0.4")
            })

    def test_allocation_negative_percentage(self):
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="between 0 and 1"):
            portfolio.set_target_allocation({
                "AAPL": Decimal("-0.1"),
                "META": Decimal("1.1")
            })

    def test_allocation_over_100_percent(self):
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="between 0 and 1"):
            portfolio.set_target_allocation({
                "AAPL": Decimal("1.5"),
                "META": Decimal("-0.5")
            })


class TestRebalance:
    def test_rebalance_no_target_raises(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("185")))
        with pytest.raises(ValueError, match="No target allocation"):
            portfolio.rebalance()

    def test_rebalance_empty_portfolio(self):
        portfolio = Portfolio()
        portfolio.set_target_allocation({"AAPL": Decimal("1.0")})
        assert portfolio.rebalance() == []

    def test_rebalance_already_balanced(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("100")))
        portfolio.add_stock(Stock("META", 10, Decimal("100")))
        portfolio.set_target_allocation({
            "AAPL": Decimal("0.5"),
            "META": Decimal("0.5")
        })
        orders = portfolio.rebalance()
        assert orders == []

    def test_rebalance_basic_buy_sell(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 27, Decimal("185")))
        portfolio.add_stock(Stock("META", 8, Decimal("580")))

        portfolio.set_target_allocation({
            "AAPL": Decimal("0.6"),
            "META": Decimal("0.4")
        })

        orders = portfolio.rebalance()
        order_by_symbol = {o.symbol: o for o in orders}

        if "AAPL" in order_by_symbol:
            aapl_order = order_by_symbol["AAPL"]
            assert aapl_order.action == "BUY"
            assert aapl_order.shares == 4

        if "META" in order_by_symbol:
            meta_order = order_by_symbol["META"]
            assert meta_order.action == "SELL"
            assert meta_order.shares == 1

    def test_rebalance_sell_unlisted_holdings(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("100")))
        portfolio.add_stock(Stock("GOOG", 5, Decimal("200")))

        portfolio.set_target_allocation({"AAPL": Decimal("1.0")})

        orders = portfolio.rebalance()
        goog_orders = [o for o in orders if o.symbol == "GOOG"]

        assert len(goog_orders) == 1
        assert goog_orders[0].action == "SELL"
        assert goog_orders[0].shares == 5

    def test_rebalance_new_stock_with_price_lookup(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 10, Decimal("100")))

        portfolio.set_target_allocation({
            "AAPL": Decimal("0.5"),
            "META": Decimal("0.5")
        })

        with pytest.raises(ValueError, match="no price provided"):
            portfolio.rebalance()

        orders = portfolio.rebalance(price_lookup={"META": Decimal("100")})
        meta_orders = [o for o in orders if o.symbol == "META"]

        assert len(meta_orders) == 1
        assert meta_orders[0].action == "BUY"

    def test_rebalance_deviation_tracking(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("CASH", 1, Decimal("1000")))

        portfolio.set_target_allocation({
            "META": Decimal("1.0")
        })

        orders = portfolio.rebalance(price_lookup={"META": Decimal("580")})

        meta_orders = [o for o in orders if o.symbol == "META"]
        assert len(meta_orders) == 1

        order = meta_orders[0]
        assert order.action == "BUY"
        assert order.shares == 1
        assert order.dollar_amount == Decimal("580")
        assert order.target_dollars == Decimal("1000")
        assert order.deviation_dollars == Decimal("420")

    def test_rebalance_small_delta_no_trade(self):
        portfolio = Portfolio()
        portfolio.add_stock(Stock("AAPL", 1, Decimal("100")))

        portfolio.set_target_allocation({
            "AAPL": Decimal("0.9"),
            "META": Decimal("0.1")
        })

        orders = portfolio.rebalance(price_lookup={"META": Decimal("580")})

        meta_orders = [o for o in orders if o.symbol == "META"]
        assert len(meta_orders) == 0
