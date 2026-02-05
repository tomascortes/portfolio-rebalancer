"""Loaders for importing portfolio data from external sources."""

from decimal import Decimal
from urllib.parse import urlparse

from .config import FintualConfig, FintualFund
from .scrapers.fintual import scrape_fintual_sync


def load_fintual_allocation(
    fund: str | FintualFund = FintualFund.RISKY_NORRIS,
) -> dict[str, Decimal]:
    """Load portfolio allocation from a Fintual fund.

    Args:
        fund: Fund identifier (e.g., "risky-norris") or FintualFund enum value.
            Defaults to RISKY_NORRIS.

    Returns:
        Dictionary mapping asset symbols to their allocation percentages (as decimals 0-1).

    Example:
        >>> allocation = load_fintual_allocation()  # defaults to risky-norris
        >>> allocation = load_fintual_allocation("moderate-pitt")
        >>> allocation = load_fintual_allocation(FintualFund.CONSERVATIVE_CLOONEY)
    """
    return scrape_fintual_sync(fund)


def load_from_url(url: str) -> dict[str, Decimal]:
    """Load portfolio allocation from a URL.

    Currently supports:
        - fintual.cl fund pages (e.g., https://fintual.cl/risky-norris)

    Args:
        url: URL to scrape allocation from.

    Returns:
        Dictionary mapping asset symbols to their allocation percentages (as decimals 0-1).

    Raises:
        ValueError: If the URL is not supported.
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if hostname in ("fintual.cl", "www.fintual.cl"):
        fund_slug = _extract_fintual_fund_from_path(parsed.path)
        return load_fintual_allocation(fund_slug)

    raise ValueError(f"Unsupported URL: {url}. Currently only fintual.cl is supported.")


def _extract_fintual_fund_from_path(path: str) -> str:
    """Extract the fund slug from a Fintual URL path.

    Args:
        path: URL path (e.g., "/risky-norris" or "/risky-norris/").

    Returns:
        Fund slug (e.g., "risky-norris").

    Raises:
        ValueError: If the path doesn't contain a valid fund slug.
    """
    path = path.strip("/")
    if not path:
        raise ValueError("No fund specified in URL path")

    parts = path.split("/")
    fund_slug = parts[0]

    valid_slugs = {f.value for f in FintualFund}
    if fund_slug not in valid_slugs:
        raise ValueError(
            f"Unknown Fintual fund: '{fund_slug}'. "
            f"Valid funds are: {', '.join(valid_slugs)}"
        )

    return fund_slug
