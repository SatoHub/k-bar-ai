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
_BROWSER_LAUNCH_TIMEOUT = 30  # seconds
_PAGE_TIMEOUT = 30000  # milliseconds


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
        "--disable-extensions",
        "--disable-background-networking",
    ]

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._pw = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BaseScraper":
        try:
            async with asyncio.timeout(_BROWSER_LAUNCH_TIMEOUT):
                self._pw = await async_playwright().start()
                await self._launch_browser()
        except TimeoutError:
            raise RuntimeError(
                f"Browser launch timed out after {_BROWSER_LAUNCH_TIMEOUT}s"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
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
            logger.warning("Browser disconnected, re-launching...")
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
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            page: Page | None = None
            try:
                if attempt > 0:
                    backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    logger.info(
                        "Retry %d/%d, backoff %ds for %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                        url,
                    )
                    await asyncio.sleep(backoff)

                await self._ensure_browser()
                page = await self._browser.new_page()
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT
                )
                if response and response.status >= 400:
                    logger.warning("HTTP %d for %s", response.status, url)
                    if attempt < _MAX_RETRIES - 1:
                        continue
                    raise RuntimeError(f"HTTP {response.status} for {url}")

                html = await page.content()
                logger.info("Fetched %s (%d bytes)", url, len(html))
                return html

            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        url,
                        e,
                    )
                # else: will raise after loop

            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

        raise RuntimeError(
            f"Failed after {_MAX_RETRIES} retries: {url}"
        ) from last_error

    async def fetch_json(self, url: str) -> dict:
        """Fetch a JSON API endpoint with retries.

        Returns parsed JSON dict.
        """
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            page: Page | None = None
            try:
                if attempt > 0:
                    backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    await asyncio.sleep(backoff)

                await self._ensure_browser()
                page = await self._browser.new_page()
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT
                )
                if response and response.status >= 400:
                    if attempt < _MAX_RETRIES - 1:
                        continue
                    raise RuntimeError(f"HTTP {response.status} for {url}")

                text = await page.inner_text("body")
                import json

                return json.loads(text)

            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Attempt %d/%d failed for JSON %s: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        url,
                        e,
                    )

            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

        raise RuntimeError(
            f"Failed after {_MAX_RETRIES} retries: {url}"
        ) from last_error
