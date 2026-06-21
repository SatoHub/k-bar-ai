"""荒れ対応ヘッジ: 本命=三連複 / 穴=ワイド の2本立て提案。

人気で決着→三連複、穴が突っ込む→穴ワイド、で互いをカバー。各サイドとも
ガミ防止配分。穴は sleeper 検出(netkeibaの全成績)で抽出するため時間がかかる。
"""

from __future__ import annotations

import logging
from itertools import combinations, permutations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bet_suggestion import suggest
from app.services.bet_suggestion_service import ENGINE_TO_NK
from app.services.prediction_service import get_race_predictions
from app.services.race_service import get_race_detail
from app.services.sleeper_service import find_sleepers

logger = logging.getLogger(__name__)

BET_JA = {
    "tansho": "単勝", "fukusho": "複勝", "umaren": "馬連",
    "wide": "ワイド", "umatan": "馬単", "trio": "三連複", "trifecta": "三連単",
}


def _uniq(seq):
    return list(dict.fromkeys(seq))


def _leg_combos(bet: str, pool: list[int]) -> list[tuple]:
    """指定した馬プールの中だけで券種別の買い目を生成。
    本命=人気上位プール、穴=穴馬プール、と同じロジックで各サイドを組む。
    """
    p = pool
    if len(p) < 1:
        return []
    if bet in ("tansho", "fukusho"):
        return [(p[0],)]
    if bet == "wide":
        return _uniq([tuple(sorted(c)) for c in combinations(p[:4], 2)])
    if bet == "umaren":
        return _uniq([tuple(sorted(c)) for c in combinations(p[:4], 2)])
    if bet == "umatan":  # 先頭軸の1・2着マルチ
        return _uniq([(p[0], b) for b in p[1:4]] + [(a, p[0]) for a in p[1:4]])
    if bet == "trio":
        return _uniq([tuple(sorted((p[0], *c))) for c in combinations(p[1:6], 2)])
    if bet == "trifecta":  # 先頭1頭マルチ
        res = []
        for c in combinations(p[1:6], 2):
            res += list(permutations((p[0], *c)))
        return _uniq(res)
    return []


async def suggest_hedge(
    session: AsyncSession,
    race_id_str: str,
    budget: int,
    honmei_ratio: float = 0.5,  # 本命に回す比率
    min_fav: int = 5,
    honmei_bet: str = "trio",  # 本命サイドの券種
    ana_bet: str = "wide",  # 穴サイドの券種
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

    # 穴馬を検出（応答時間短縮のため頭数を抑制）
    sleepers_res = await find_sleepers(session, race_id_str, min_fav=min_fav, max_horses=10)
    sleeper_entries = (sleepers_res or {}).get("entries", [])  # 穴度の高い順

    honmei = ranked[:5]  # 本命プール = 予想(人気)上位
    honmei_set = set(honmei)

    # 穴プール = 穴馬同士の組み合わせ用。検出した穴(穴度順)を優先し、不足分は
    # 人気薄(min_fav番人気以下)で補完。本命プールとは重複させない。
    ana_pool: list[int] = []
    for e in sleeper_entries:
        p = e.get("post_position")
        if p and e.get("is_sleeper") and p not in honmei_set and p not in ana_pool:
            ana_pool.append(p)
    for h in sorted(horses, key=lambda x: (x.get("win_favorite") or 99)):
        p = h["post"]
        if (h.get("win_favorite") or 99) >= min_fav and p not in honmei_set and p not in ana_pool:
            ana_pool.append(p)
    ana_pool = ana_pool[:5]

    honmei_budget = max(0, round(budget * honmei_ratio / 100) * 100)
    ana_budget = budget - honmei_budget
    h_ja, a_ja = BET_JA.get(honmei_bet, honmei_bet), BET_JA.get(ana_bet, ana_bet)
    menu: list[dict] = []

    # 本命サイド: 人気上位の組み合わせ
    h_combos = _leg_combos(honmei_bet, honmei)
    if h_combos and honmei_budget >= 100:
        menu.append({
            "bet": honmei_bet, "method": "hedge", "combos": h_combos,
            "axis": [honmei[0]] if honmei_bet in ("trio", "trifecta", "umatan") else None,
            "horses": honmei,
            "rationale": f"本命サイド: 人気上位馬の{h_ja}(順当決着を回収)",
            "weight": 2, "budget": honmei_budget,
        })

    # 穴サイド: 穴馬同士の組み合わせ
    a_combos = _leg_combos(ana_bet, ana_pool)
    coverage = f"人気で決着→本命{h_ja} / 穴で決着→穴{a_ja}、で相互カバー。"
    if a_combos and ana_budget >= 100:
        menu.append({
            "bet": ana_bet, "method": "hedge", "combos": a_combos,
            "axis": [ana_pool[0]] if ana_bet in ("trio", "trifecta", "umatan") else None,
            "horses": ana_pool,
            "rationale": f"穴サイド: 穴馬同士の{a_ja}(波乱を拾う)",
            "weight": 1, "budget": ana_budget,
        })
    elif menu:
        coverage = f"穴馬が不足のため、本命の{h_ja}のみ。"
        menu[0]["budget"] = budget  # 全額を本命サイドへ

    sleeper_posts = ana_pool

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
    )
    res.update(base)
    res["odds_live"] = bool(odds_lookup)
    res["coverage_note"] = coverage
    res["sleeper_posts"] = sleeper_posts
    return res
