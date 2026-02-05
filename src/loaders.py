"""Loaders for importing portfolio data from external sources."""

from decimal import Decimal


def load_fintual_allocation(portfolio_name: str) -> dict[str, Decimal]:
    raise NotImplementedError(f"Fintual loader not yet implemented for '{portfolio_name}'")


def load_from_url(url: str) -> dict[str, Decimal]:
    raise NotImplementedError(f"URL loader not yet implemented for: {url}")
