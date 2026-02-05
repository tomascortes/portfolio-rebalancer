"""Tests for the Fintual scraper."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import FintualConfig, FintualFund
from src.scrapers.fintual import FintualScraper
from src.loaders import (
    load_fintual_allocation,
    load_from_url,
    _extract_fintual_fund_from_path,
)


class TestFintualConfig:
    """Tests for FintualConfig."""

    def test_default_values(self):
        config = FintualConfig()
        assert config.BASE_URL == "https://fintual.cl"
        assert config.POSITIONS_TABLE_CLASS == "_positionsTable_czfv5_1"
        assert config.DEFAULT_FUND == FintualFund.RISKY_NORRIS
        assert config.REQUEST_TIMEOUT_MS == 30000

    def test_frozen(self):
        config = FintualConfig()
        with pytest.raises(Exception):
            config.BASE_URL = "https://other.com"


class TestFintualFund:
    """Tests for FintualFund enum."""

    def test_fund_values(self):
        assert FintualFund.RISKY_NORRIS.value == "risky-norris"
        assert FintualFund.MODERATE_PITT.value == "moderate-pitt"
        assert FintualFund.CONSERVATIVE_CLOONEY.value == "conservative-clooney"
        assert FintualFund.VERY_CONSERVATIVE_STREEP.value == "very-conservative-streep"

    def test_all_funds_have_values(self):
        for fund in FintualFund:
            assert fund.value is not None
            assert len(fund.value) > 0


class TestChileanPercentageParsing:
    """Tests for Chilean number format parsing."""

    def test_parse_comma_decimal(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("25,5%")
        assert result == Decimal("0.255")

    def test_parse_period_decimal(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("25.5%")
        assert result == Decimal("0.255")

    def test_parse_integer_percentage(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("100%")
        assert result == Decimal("1")

    def test_parse_with_whitespace(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("  25,5%  ")
        assert result == Decimal("0.255")

    def test_parse_empty_string(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("")
        assert result is None

    def test_parse_invalid_string(self):
        scraper = FintualScraper()
        result = scraper._parse_chilean_percentage("abc")
        assert result is None


class TestExtractFintualFundFromPath:
    """Tests for URL path extraction."""

    def test_simple_path(self):
        result = _extract_fintual_fund_from_path("/risky-norris")
        assert result == "risky-norris"

    def test_path_with_trailing_slash(self):
        result = _extract_fintual_fund_from_path("/risky-norris/")
        assert result == "risky-norris"

    def test_path_with_extra_segments(self):
        result = _extract_fintual_fund_from_path("/moderate-pitt/something/else")
        assert result == "moderate-pitt"

    def test_empty_path(self):
        with pytest.raises(ValueError, match="No fund specified"):
            _extract_fintual_fund_from_path("")

    def test_root_path(self):
        with pytest.raises(ValueError, match="No fund specified"):
            _extract_fintual_fund_from_path("/")

    def test_invalid_fund(self):
        with pytest.raises(ValueError, match="Unknown Fintual fund"):
            _extract_fintual_fund_from_path("/unknown-fund")


class TestLoadFromUrl:
    """Tests for load_from_url function."""

    def test_unsupported_url(self):
        with pytest.raises(ValueError, match="Unsupported URL"):
            load_from_url("https://example.com/something")

    @patch("src.loaders.scrape_fintual_sync")
    def test_fintual_url(self, mock_scrape):
        mock_scrape.return_value = {"STOCK": Decimal("1")}
        result = load_from_url("https://fintual.cl/risky-norris")
        mock_scrape.assert_called_once_with("risky-norris")
        assert result == {"STOCK": Decimal("1")}

    @patch("src.loaders.scrape_fintual_sync")
    def test_fintual_www_url(self, mock_scrape):
        mock_scrape.return_value = {"STOCK": Decimal("1")}
        result = load_from_url("https://www.fintual.cl/moderate-pitt")
        mock_scrape.assert_called_once_with("moderate-pitt")


class TestLoadFintualAllocation:
    """Tests for load_fintual_allocation function."""

    @patch("src.loaders.scrape_fintual_sync")
    def test_default_fund(self, mock_scrape):
        mock_scrape.return_value = {"STOCK": Decimal("1")}
        result = load_fintual_allocation()
        mock_scrape.assert_called_once_with(FintualFund.RISKY_NORRIS)

    @patch("src.loaders.scrape_fintual_sync")
    def test_string_fund(self, mock_scrape):
        mock_scrape.return_value = {"STOCK": Decimal("1")}
        result = load_fintual_allocation("moderate-pitt")
        mock_scrape.assert_called_once_with("moderate-pitt")

    @patch("src.loaders.scrape_fintual_sync")
    def test_enum_fund(self, mock_scrape):
        mock_scrape.return_value = {"STOCK": Decimal("1")}
        result = load_fintual_allocation(FintualFund.CONSERVATIVE_CLOONEY)
        mock_scrape.assert_called_once_with(FintualFund.CONSERVATIVE_CLOONEY)


class TestPortfolioFromUrl:
    """Tests for Portfolio.from_url class method."""

    @patch("src.loaders.scrape_fintual_sync")
    def test_from_url_sets_target_allocation(self, mock_scrape):
        from src.portfolio import Portfolio

        mock_scrape.return_value = {
            "STOCK_A": Decimal("0.5"),
            "STOCK_B": Decimal("0.5"),
        }

        portfolio = Portfolio.from_url("https://fintual.cl/risky-norris")

        assert portfolio.target_allocation == {
            "STOCK_A": Decimal("0.5"),
            "STOCK_B": Decimal("0.5"),
        }
        assert portfolio.holdings == {}
