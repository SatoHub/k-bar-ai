"""Base scraper with Playwright lifecycle, rate limiting, and retry logic."""

from __future__ import annotations

import asyncio
import logging
import random

from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)

# Retry backoff seconds
_BACKOFF = (3, 10, 30)
_MAX_RETRIES = 3


class BaseScraper:
    """Async context manager for Playwright-based scraping.

    Usage:
        async with BaseScraper(headless=True) as scraper:
            html = await scraper.fetch_page("https://...")
    """

    _LAUNCH_ARGS = [
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-gpu",
        "--single-process",
        "--disable-extensions",
        "--disable-background-networking",
    ]

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._pw = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BaseScraper":
        self._pw = await async_playwright().start()
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()
        logger.info("Browser closed")

    async def _launch_browser(self) -> None:
        """Launch (or re-launch) the browser."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = await self._pw.chromium.launch(
            headless=self._headless,
            args=self._LAUNCH_ARGS,
        )
        logger.info("Browser launched (headless=%s)", self._headless)

    async def _ensure_browser(self) -> None:
        """Re-launch browser if it has crashed."""
        if not self._browser or not self._browser.is_connected():
            logger.info("Browser disconnected, re-launching...")
            await self._launch_browser()

    async def _wait(self) -> None:
        """Wait 3-10 seconds (random) between requests."""
        delay = random.uniform(3.0, 10.0)
        logger.debug("Waiting %.1f seconds", delay)
        await asyncio.sleep(delay)

    async def fetch_page(self, url: str) -> str:
        """Fetch a page with retries and rate limiting.

        Returns the page HTML content.
        Raises RuntimeError after max retries.
        """
        for attempt in range(_MAX_RETRIES):
            try:
                if attempt > 0:
                    backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    logger.info("Retry %d, backoff %ds", attempt + 1, backoff)
                    await asyncio.sleep(backoff)

                await self._ensure_browser()
                page: Page = await self._browser.new_page()
                try:
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=30000
                    )
                    if response and response.status >= 400:
                        logger.warning("HTTP %d for %s", response.status, url)
                        if attempt < _MAX_RETRIES - 1:
                            continue
                        raise RuntimeError(f"HTTP {response.status} for {url}")

                    html = await page.content()
                    logger.info("Fetched %s (%d bytes)", url, len(html))
                    return html
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass

            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"Failed after {_MAX_RETRIES} retries: {url}"
                    ) from e
                logger.warning("Attempt %d failed: %s", attempt + 1, e)

        raise RuntimeError(f"Failed to fetch: {url}")  # unreachable

    async def fetch_json(self, url: str) -> dict:
        """Fetch a JSON API endpoint with retries.

        Returns parsed JSON dict.
        """
        for attempt in range(_MAX_RETRIES):
            try:
                if attempt > 0:
                    backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    await asyncio.sleep(backoff)

                await self._ensure_browser()
                page: Page = await self._browser.new_page()
                try:
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=30000
                    )
                    if response and response.status >= 400:
                        if attempt < _MAX_RETRIES - 1:
                            continue
                        raise RuntimeError(f"HTTP {response.status} for {url}")

                    text = await page.inner_text("body")
                    import json

                    return json.loads(text)
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass

            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"Failed after {_MAX_RETRIES} retries: {url}"
                    ) from e
                logger.warning("Attempt %d failed for JSON: %s", attempt + 1, e)

        raise RuntimeError(f"Failed to fetch JSON: {url}")
