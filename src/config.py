"""Configuration constants for the portfolio rebalancer."""

from dataclasses import dataclass
from enum import Enum


class FintualFund(Enum):
    """Available Fintual fund types."""

    RISKY_NORRIS = "risky-norris"
    MODERATE_PITT = "moderate-pitt"
    CONSERVATIVE_CLOONEY = "conservative-clooney"
    VERY_CONSERVATIVE_STREEP = "very-conservative-streep"


@dataclass(frozen=True)
class FintualConfig:
    """Configuration for Fintual scraper."""

    BASE_URL: str = "https://fintual.cl"
    POSITIONS_TABLE_CLASS: str = "_positionsTable_czfv5_1"
    DEFAULT_FUND: FintualFund = FintualFund.RISKY_NORRIS
    REQUEST_TIMEOUT_MS: int = 30000
