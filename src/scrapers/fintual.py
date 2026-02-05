"""Scraper for Fintual.cl fund allocations."""

import asyncio
import re
from decimal import Decimal
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

from ..config import FintualConfig, FintualFund


class FintualScraper:
    """Scraper for fetching portfolio allocations from Fintual.cl."""

    def __init__(self, config: Optional[FintualConfig] = None) -> None:
        self.config = config or FintualConfig()
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def scrape(self, fund: str | FintualFund = FintualFund.RISKY_NORRIS) -> dict[str, Decimal]:
        if isinstance(fund, FintualFund):
            fund_slug = fund.value
        else:
            fund_slug = fund

        url = f"{self.config.BASE_URL}/{fund_slug}"
        browser = await self._ensure_browser()
        page: Page = await browser.new_page()

        try:
            await page.goto(url, timeout=self.config.REQUEST_TIMEOUT_MS)
            await page.wait_for_selector(
                f".{self.config.POSITIONS_TABLE_CLASS}",
                timeout=self.config.REQUEST_TIMEOUT_MS
            )

            allocation = await self._parse_allocation_table(page)
            return allocation
        finally:
            await page.close()

    async def _parse_allocation_table(self, page: Page) -> dict[str, Decimal]:
        table_selector = f".{self.config.POSITIONS_TABLE_CLASS}"
        container = await page.query_selector(table_selector)

        if not container:
            return {}

        allocation: dict[str, Decimal] = {}

        children = await container.query_selector_all(":scope > *")

        current_symbol: Optional[str] = None

        for child in children:
            tag_name = await child.evaluate("el => el.tagName.toLowerCase()")

            if tag_name == "span":
                # Extract symbol from text like "ESGV: Vanguard ESG US Stock ETF"
                text = await child.inner_text()
                if ":" in text:
                    current_symbol = text.split(":")[0].strip()
                else:
                    current_symbol = text.strip()

            elif tag_name == "p" and current_symbol:
                # This should be the percentage following the symbol
                text = await child.inner_text()
                if "%" in text:
                    percentage = self._parse_chilean_percentage(text)
                    if percentage is not None:
                        allocation[current_symbol] = percentage
                    current_symbol = None

        return allocation

    def _parse_chilean_percentage(self, text: str) -> Optional[Decimal]:
        text = text.strip()
        text = text.replace("%", "")
        text = text.replace(",", ".")
        text = re.sub(r"[^\d.]", "", text)

        if not text:
            return None

        try:
            value = Decimal(text) / Decimal("100")
            return value
        except Exception:
            return None

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


def scrape_fintual_sync(
    fund: str | FintualFund = FintualFund.RISKY_NORRIS,
    config: Optional[FintualConfig] = None,
) -> dict[str, Decimal]:

    async def _run() -> dict[str, Decimal]:
        scraper = FintualScraper(config)
        try:
            return await scraper.scrape(fund)
        finally:
            await scraper.close()

    return asyncio.run(_run())
