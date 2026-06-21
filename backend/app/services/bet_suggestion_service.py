"""予算指定の買い目提案 — オーケストレーション層。

予想(予想順・荒れ度)・出走馬(馬番/単勝オッズ/人気)・ライブのcombo別オッズを
集めて、純粋エンジン app.services.bet_suggestion.suggest() を呼ぶ。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bet_suggestion import _build_menu, suggest
from app.services.prediction_service import get_race_predictions
from app.services.race_service import get_race_detail

logger = logging.getLogger(__name__)

# エンジンの券種名 → netkeiba odds の券種名
ENGINE_TO_NK = {
    "fukusho": "fukusho",
    "wide": "wide",
    "umaren": "umaren",
    "trio": "sanrenpuku",
    "trifecta": "sanrentan",
}


async def suggest_bets(
    session: AsyncSession,
    race_id_str: str,
    budget: int,
    alloc_mode: str = "gami_avoid",
    bet_types: list[str] | None = None,
    type_budgets: dict[str, int] | None = None,
) -> dict | None:
    race = await get_race_detail(session, race_id_str)
    if not race:
        return None

    pred = await get_race_predictions(session, race_id_str)
    predictions = (pred or {}).get("predictions", [])

    post_by_horse: dict = {}
    horses: list[dict] = []
    names: dict[int, str] = {}
    for e in race.entries:
        post_by_horse[e.horse_id] = e.post_position
        if e.post_position and e.horse:
            names[e.post_position] = e.horse.name
        if e.post_position and e.win_odds:
            horses.append({
                "post": e.post_position,
                "win_odds": float(e.win_odds),
                "win_favorite": e.win_favorite,
            })

    ranked_pairs = []
    for p in predictions:
        post = post_by_horse.get(p["horse_id"])
        if post and p.get("predicted_position"):
            ranked_pairs.append((p["predicted_position"], post))
    ranked = [post for _, post in sorted(ranked_pairs)]

    base = {
        "race_id": race_id_str,
        "race_name": race.race_name,
        "budget": budget,
        "alloc_mode": alloc_mode,
        "names": {str(k): v for k, v in names.items()},
    }
    if not horses or not ranked:
        return {**base, "upset_level": "mid", "odds_live": False,
                "total_allocated": 0, "suggestions": [],
                "message": "予想またはオッズが未取得のため提案できません"}

    level = ((pred or {}).get("upset") or {}).get("level") or "mid"

    # この提案で使う券種を決め、その券種だけライブオッズを取得
    by_post = {h["post"]: h for h in horses}
    if bet_types:
        needed = [t for t in bet_types if t in ENGINE_TO_NK]
    else:
        needed = [m["bet"] for m in _build_menu(ranked, by_post, level)]

    odds_lookup: dict[str, dict] = {}
    if needed:
        from app.scraper.netkeiba import NetkeibaScraper
        try:
            async with NetkeibaScraper(headless=True) as nk:
                for t in set(needed):
                    try:
                        parsed = await nk.scrape_full_odds(race_id_str, ENGINE_TO_NK[t])
                        if parsed and parsed.get("combos"):
                            odds_lookup[t] = {
                                k: v["odds"]
                                for k, v in parsed["combos"].items()
                                if v.get("odds")
                            }
                    except Exception as e:  # noqa: BLE001
                        logger.warning("odds fetch failed for %s/%s: %s", race_id_str, t, e)
        except Exception as e:  # noqa: BLE001
            logger.warning("odds scraper session failed: %s", e)

    res = suggest(
        budget, horses, ranked, level,
        odds_lookup=odds_lookup or None,
        alloc_mode=alloc_mode,
        bet_types=bet_types,
        type_budgets=type_budgets,
    )
    res.update(base)
    res["odds_live"] = bool(odds_lookup)
    return res
