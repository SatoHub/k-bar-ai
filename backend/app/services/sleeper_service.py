"""巻き返し穴(sleeper)検出 — オーケストレーション層。

出走馬のうち人気薄(>=min_fav番人気)について netkeiba の全成績をスクレイプし、
今走の馬場での実力 vs 人気の乖離から sleeper 度を算出して返す。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.race_service import get_race_detail
from app.services.sleeper import compute_sleeper

logger = logging.getLogger(__name__)


async def find_sleepers(
    session: AsyncSession,
    race_id_str: str,
    min_fav: int = 5,
    max_horses: int = 14,
) -> dict | None:
    race = await get_race_detail(session, race_id_str)
    if not race:
        return None

    surface = race.surface
    rdate = race.race_date

    targets = [
        e for e in race.entries
        if e.win_favorite and e.win_favorite >= min_fav
        and e.horse and e.horse.netkeiba_id
    ]
    targets.sort(key=lambda e: e.win_favorite)
    targets = targets[:max_horses]

    base = {"race_id": race_id_str, "surface": surface}
    if not targets:
        return {**base, "analyzed": 0, "entries": [],
                "message": "人気薄の出走馬(またはnetkeiba_id)がありません"}

    from app.scraper.netkeiba import NetkeibaScraper

    entries = []
    async with NetkeibaScraper(headless=True) as nk:
        for e in targets:
            try:
                career = await nk.scrape_horse_career(e.horse.netkeiba_id)
            except Exception as ex:  # noqa: BLE001
                logger.warning("career fetch failed %s: %s", e.horse.netkeiba_id, ex)
                continue
            s = compute_sleeper(surface, e.win_favorite, career, before_date=rdate)
            entries.append({
                "post_position": e.post_position,
                "bracket_number": e.bracket_number,
                "horse_name": e.horse.name,
                "win_favorite": e.win_favorite,
                "is_sleeper": s["is_sleeper"],
                "score": s["score"],
                "reason": s["reason"],
                "surface_runs": s["surface_runs"],
                "surface_place_rate": s["surface_place_rate"],
                "has_win": s["has_win"],
                "graded_good": s["graded_good"],
                "surface_mismatch": s["surface_mismatch"],
            })

    entries.sort(key=lambda x: -x["score"])
    return {**base, "analyzed": len(entries), "entries": entries}
