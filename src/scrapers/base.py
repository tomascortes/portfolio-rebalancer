"""Abstract base class for portfolio scrapers."""

from abc import ABC, abstractmethod
from decimal import Decimal


class BaseScraper(ABC):
    """Abstract base class for portfolio allocation scrapers."""

    @abstractmethod
    async def scrape(self, identifier: str) -> dict[str, Decimal]:
        """Scrape portfolio allocation from the source.

        Args:
            identifier: Fund identifier or URL path component.

        Returns:
            Dictionary mapping asset symbols to their allocation percentages (as decimals 0-1).
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (browser, connections, etc.)."""
        pass
