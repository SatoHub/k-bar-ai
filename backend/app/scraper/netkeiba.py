"""NetkeibaScraper: scrape race lists, shutuba, odds, and results from netkeiba.com."""

from __future__ import annotations

import asyncio
import logging

from app.scraper.base import BaseScraper
from app.scraper.parsers.odds import (
    NETKEIBA_ODDS_TYPE_MAP,
    parse_combo_odds,
    parse_full_odds,
    parse_odds_json,
)
from app.scraper.parsers.race_list import parse_race_list
from app.scraper.parsers.result import parse_result
from app.scraper.parsers.shutuba import parse_shutuba

logger = logging.getLogger(__name__)

# URL templates
_RACE_LIST_URL = "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date}"
_SHUTUBA_URL = "https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
_ODDS_API_URL = (
    "https://race.netkeiba.com/api/api_get_jra_odds.html"
    "?race_id={race_id}&type=1&action=update"
)
_ODDS_API_URL_TYPED = (
    "https://race.netkeiba.com/api/api_get_jra_odds.html"
    "?race_id={race_id}&type={odds_type}&action=update"
)
_RESULT_URL = "https://race.netkeiba.com/race/result.html?race_id={race_id}"
_HORSE_CAREER_URL = "https://db.netkeiba.com/horse/result/{netkeiba_id}/"


class NetkeibaScraper:
    """High-level scraper for netkeiba.com.

    Usage:
        async with NetkeibaScraper(headless=True) as nk:
            races = await nk.scrape_race_list("20260222")
            shutuba = await nk.scrape_shutuba("202505021211")
    """

    def __init__(self, *, headless: bool = True) -> None:
        self._base = BaseScraper(headless=headless)

    async def __aenter__(self) -> "NetkeibaScraper":
        await self._base.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._base.__aexit__(exc_type, exc_val, exc_tb)

    async def scrape_race_list(self, date_str: str) -> list[dict]:
        """Scrape race list for a given date (YYYYMMDD format).

        Returns list of race info dicts with race_id, race_number, etc.
        """
        url = _RACE_LIST_URL.format(date=date_str)
        html = await self._base.fetch_page(url)
        races = parse_race_list(html)
        logger.info("Found %d races for %s", len(races), date_str)
        return races

    async def scrape_shutuba(self, race_id: str) -> dict:
        """Scrape shutuba (出馬表) for a specific race.

        Returns parsed shutuba dict with race info and entries.
        """
        url = _SHUTUBA_URL.format(race_id=race_id)
        await self._base._wait()
        html = await self._base.fetch_page(url)
        result = parse_shutuba(html, race_id)
        logger.info("Shutuba %s: %d entries", race_id, len(result.get("entries", [])))
        return result

    async def scrape_odds(self, race_id: str) -> list[dict]:
        """Scrape win odds for a specific race via API.

        Returns list of odds dicts with post_position, win_odds, win_favorite.
        """
        url = _ODDS_API_URL.format(race_id=race_id)
        await self._base._wait()
        data = await self._base.fetch_json(url)
        odds = parse_odds_json(data, race_id)
        logger.info("Odds %s: %d entries", race_id, len(odds))
        return odds

    async def scrape_combo_odds(
        self, race_id: str, bet_type: str, selections: list[int]
    ) -> float | None:
        """Scrape odds for a specific bet type and horse combination.

        Args:
            race_id: Race identifier (e.g. "202605010811").
            bet_type: One of tansho, fukusho, wakuren, umaren, umatan, wide, sanrenpuku, sanrentan.
            selections: Horse numbers (post_position) or bracket numbers.

        Returns:
            Odds value as float, or None if unavailable.
        """
        type_info = NETKEIBA_ODDS_TYPE_MAP.get(bet_type)
        if not type_info:
            return None
        url = _ODDS_API_URL_TYPED.format(
            race_id=race_id, odds_type=type_info["api_type"]
        )
        await self._base._wait()
        data = await self._base.fetch_json(url)
        odds = parse_combo_odds(data, bet_type, selections)
        logger.info(
            "ComboOdds %s %s %s: %s", race_id, bet_type, selections, odds
        )
        return odds

    async def scrape_full_odds(self, race_id: str, bet_type: str) -> dict | None:
        """Scrape the FULL odds table for one bet type in a single request.

        One typed-odds response holds every combination for the bet type, so a
        box/formation/nagashi selection only needs one fetch per bet type; each
        combo is then looked up locally on the client.

        Args:
            race_id: Race identifier (e.g. "202605010811").
            bet_type: One of tansho, fukusho, wakuren, umaren, umatan, wide,
                      sanrenpuku, sanrentan.

        Returns:
            Parsed dict from parse_full_odds (status / official_datetime /
            combos), or None if unavailable.
        """
        type_info = NETKEIBA_ODDS_TYPE_MAP.get(bet_type)
        if not type_info:
            return None
        url = _ODDS_API_URL_TYPED.format(
            race_id=race_id, odds_type=type_info["api_type"]
        )
        await self._base._wait()
        data = await self._base.fetch_json(url)
        result = parse_full_odds(data, bet_type)
        logger.info(
            "FullOdds %s %s: %d combos",
            race_id,
            bet_type,
            len(result["combos"]) if result else 0,
        )
        return result

    async def scrape_result(self, race_id: str) -> dict:
        """Scrape race result for a specific race.

        Returns parsed result dict with race info and entries.
        """
        url = _RESULT_URL.format(race_id=race_id)
        await self._base._wait()
        html = await self._base.fetch_page(url)
        result = parse_result(html, race_id)
        logger.info("Result %s: %d entries", race_id, len(result.get("entries", [])))
        return result

    async def scrape_horse_career(self, netkeiba_id: str) -> list[dict]:
        """Scrape a horse's full career results (surface-split) from netkeiba."""
        from app.scraper.parsers.horse_career import parse_horse_career

        url = _HORSE_CAREER_URL.format(netkeiba_id=netkeiba_id)
        # 馬ごとに連続取得するため待機は短め(1秒)。db.netkeibaは軽いページ。
        await asyncio.sleep(1.0)
        html = await self._base.fetch_page(url)
        runs = parse_horse_career(html)
        logger.info("Career %s: %d runs", netkeiba_id, len(runs))
        return runs

    async def scrape_day(
        self,
        date_str: str,
        *,
        include_odds: bool = True,
        include_result: bool = False,
    ) -> dict:
        """Scrape all races for a given date.

        Args:
            date_str: Date in YYYYMMDD format.
            include_odds: Whether to also scrape odds.
            include_result: Whether to also scrape results (for past races).

        Returns:
            {
                "date": "20260222",
                "races": [
                    {
                        "race_list_info": {...},
                        "shutuba": {...},
                        "odds": [...] or None,
                        "result": {...} or None,
                    },
                    ...
                ]
            }
        """
        race_list = await self.scrape_race_list(date_str)
        logger.info("Processing %d races for %s", len(race_list), date_str)

        all_races = []
        for race_info in race_list:
            race_id = race_info["race_id"]
            race_data: dict = {"race_list_info": race_info}

            # Shutuba
            race_data["shutuba"] = await self.scrape_shutuba(race_id)

            # Odds
            if include_odds:
                try:
                    race_data["odds"] = await self.scrape_odds(race_id)
                except Exception as e:
                    logger.warning("Failed to scrape odds for %s: %s", race_id, e)
                    race_data["odds"] = None
            else:
                race_data["odds"] = None

            # Result
            if include_result:
                try:
                    race_data["result"] = await self.scrape_result(race_id)
                except Exception as e:
                    logger.warning("Failed to scrape result for %s: %s", race_id, e)
                    race_data["result"] = None
            else:
                race_data["result"] = None

            all_races.append(race_data)

        return {"date": date_str, "races": all_races}
