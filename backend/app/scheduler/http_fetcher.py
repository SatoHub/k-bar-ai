"""Lightweight HTTP fetcher for netkeiba race_list_sub.html.

Uses httpx instead of Playwright since race_list_sub.html is a static HTML fragment.
"""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from app.scraper.parsers.race_list import parse_race_list

logger = logging.getLogger(__name__)

_RACE_LIST_URL = "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

_MAX_RETRIES = 3
_BACKOFF = (3, 10, 30)


async def fetch_race_list(date_str: str) -> list[dict]:
    """Fetch and parse race list for a date (YYYYMMDD format).

    Returns list of race info dicts from parse_race_list().
    """
    url = _RACE_LIST_URL.format(date=date_str)

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30.0) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                if attempt > 0:
                    backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    logger.info("Retry %d, backoff %ds", attempt + 1, backoff)
                    await asyncio.sleep(backoff)

                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                races = parse_race_list(html)
                logger.info("httpx: Found %d races for %s", len(races), date_str)
                return races

            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    logger.error("Failed to fetch race list for %s: %s", date_str, e)
                    raise
                logger.warning("Attempt %d failed: %s", attempt + 1, e)

    return []  # unreachable


async def fetch_race_lists_multi(date_strings: list[str]) -> dict[str, list[dict]]:
    """Fetch race lists for multiple dates with rate limiting.

    Returns {date_str: [race_info, ...]} mapping.
    """
    results: dict[str, list[dict]] = {}

    for date_str in date_strings:
        try:
            races = await fetch_race_list(date_str)
            results[date_str] = races
        except Exception as e:
            logger.warning("Skipping %s: %s", date_str, e)
            results[date_str] = []

        # Rate limit: 1-3 seconds between requests
        await asyncio.sleep(random.uniform(1.0, 3.0))

    return results
