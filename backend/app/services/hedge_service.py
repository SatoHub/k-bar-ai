"""荒れ対応ヘッジ: 本命=三連複 / 穴=ワイド の2本立て提案。

人気で決着→三連複、穴が突っ込む→穴ワイド、で互いをカバー。各サイドとも
ガミ防止配分。穴は sleeper 検出(netkeibaの全成績)で抽出するため時間がかかる。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bet_suggestion import suggest
from app.services.bet_suggestion_service import ENGINE_TO_NK
from app.services.prediction_service import get_race_predictions
from app.services.race_service import get_race_detail
from app.services.sleeper_service import find_sleepers

logger = logging.getLogger(__name__)


async def suggest_hedge(
    session: AsyncSession,
    race_id_str: str,
    budget: int,
    honmei_ratio: float = 0.5,  # 本命(三連複)に回す比率
    min_fav: int = 5,
) -> dict | None:
    race = await get_race_detail(session, race_id_str)
    if not race:
        return None

    pred = await get_race_predictions(session, race_id_str)
    predictions = (pred or {}).get("predictions", [])
    level = ((pred or {}).get("upset") or {}).get("level") or "mid"

    post_by_horse, horses, names = {}, [], {}
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

    ranked_pairs = [
        (p["predicted_position"], post_by_horse.get(p["horse_id"]))
        for p in predictions
        if p.get("predicted_position") and post_by_horse.get(p["horse_id"])
    ]
    ranked = [post for _, post in sorted(ranked_pairs)]

    base = {
        "race_id": race_id_str, "race_name": race.race_name, "budget": budget,
        "alloc_mode": "gami_avoid", "upset_level": level,
        "names": {str(k): v for k, v in names.items()},
    }
    if not horses or len(ranked) < 4:
        return {**base, "odds_live": False, "total_allocated": 0, "suggestions": [],
                "message": "予想またはオッズが不足しています"}

    # 穴馬を検出（is_sleeper のみ採用）。応答時間短縮のため頭数を抑制。
    sleepers_res = await find_sleepers(session, race_id_str, min_fav=min_fav, max_horses=10)
    sleeper_posts = [
        e["post_position"] for e in (sleepers_res or {}).get("entries", [])
        if e.get("is_sleeper") and e.get("post_position")
    ]

    honmei = ranked[:5]
    honmei_budget = max(0, round(budget * honmei_ratio / 100) * 100)
    ana_budget = budget - honmei_budget

    menu: list[dict] = []
    type_budgets: dict[str, int] = {}
    # 本命サイド: 三連複(本命軸→相手)
    menu.append({
        "bet": "trio", "method": "nagashi", "axis": [ranked[0]],
        "partners": ranked[1:6],
        "rationale": "本命サイド: 人気上位で三連複(順当決着を回収)", "weight": 1,
    })
    type_budgets["trio"] = honmei_budget

    coverage = "人気で決着→三連複 / 穴が来る→穴ワイド、で相互カバー。"
    if sleeper_posts:
        # 穴サイド: 穴 ×（上位人気＋他の穴）のワイド
        partners = [p for p in honmei if p not in sleeper_posts]
        partners += [p for p in sleeper_posts]  # 穴×穴 も少し拾う
        menu.append({
            "bet": "wide", "method": "formation",
            "sets": [sleeper_posts, partners],
            "rationale": "穴サイド: 穴×上位/他穴のワイド(一発を拾う)", "weight": 1,
        })
        type_budgets["wide"] = ana_budget
    else:
        # 穴が無ければ全額を本命三連複へ
        type_budgets["trio"] = budget
        coverage = "穴候補が検出されなかったため、本命の三連複のみ。"

    # ライブオッズ取得(trio / wide)
    odds_lookup: dict[str, dict] = {}
    needed = {m["bet"] for m in menu}
    from app.scraper.netkeiba import NetkeibaScraper
    try:
        async with NetkeibaScraper(headless=True) as nk:
            for t in needed:
                try:
                    parsed = await nk.scrape_full_odds(race_id_str, ENGINE_TO_NK[t])
                    if parsed and parsed.get("combos"):
                        odds_lookup[t] = {
                            k: v["odds"] for k, v in parsed["combos"].items() if v.get("odds")
                        }
                except Exception as e:  # noqa: BLE001
                    logger.warning("hedge odds fetch failed %s: %s", t, e)
    except Exception as e:  # noqa: BLE001
        logger.warning("hedge odds scraper failed: %s", e)

    res = suggest(
        budget, horses, ranked, level,
        odds_lookup=odds_lookup or None,
        alloc_mode="gami_avoid",
        menu_override=menu,
        type_budgets=type_budgets,
    )
    res.update(base)
    res["odds_live"] = bool(odds_lookup)
    res["coverage_note"] = coverage
    res["sleeper_posts"] = sleeper_posts
    return res
