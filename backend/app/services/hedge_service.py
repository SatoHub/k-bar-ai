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


def _honmei_combos(bet: str, h: list[int]) -> list[tuple]:
    """本命サイド: 予想上位馬での買い目。"""
    if len(h) < 1:
        return []
    if bet in ("tansho", "fukusho"):
        return [(h[0],)]
    if bet == "wide":
        return [tuple(sorted(c)) for c in combinations(h[:3], 2)]
    if bet == "umaren":
        return [tuple(sorted(c)) for c in combinations(h[:4], 2)]
    if bet == "umatan":  # 軸の1・2着マルチ
        return _uniq([(h[0], b) for b in h[1:4]] + [(a, h[0]) for a in h[1:4]])
    if bet == "trio":
        return _uniq([tuple(sorted((h[0], *c))) for c in combinations(h[1:6], 2)])
    if bet == "trifecta":  # 軸1頭マルチ
        res = []
        for c in combinations(h[1:6], 2):
            res += list(permutations((h[0], *c)))
        return _uniq(res)
    return []


def _ana_combos(bet: str, ana: list[int], partners: list[int]) -> list[tuple]:
    """穴サイド: 穴馬 ×（上位＋他穴）の買い目。"""
    if not ana:
        return []
    if bet in ("tansho", "fukusho"):
        return [(a,) for a in ana]
    if bet in ("wide", "umaren"):
        pairs = [tuple(sorted((a, p))) for a in ana for p in partners if a != p]
        return _uniq(pairs)
    if bet == "umatan":  # 穴が1着/2着の両取り
        return _uniq([(a, p) for a in ana for p in partners if a != p]
                     + [(p, a) for a in ana for p in partners if a != p])
    if bet == "trio":  # 穴1頭軸 + 相手2頭
        res = []
        for a in ana:
            rest = [p for p in partners if p != a]
            res += [tuple(sorted((a, *c))) for c in combinations(rest, 2)]
        return _uniq(res)
    if bet == "trifecta":  # 穴1頭マルチ
        res = []
        for a in ana:
            rest = [p for p in partners if p != a]
            for c in combinations(rest, 2):
                res += list(permutations((a, *c)))
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

    # 穴馬を検出（is_sleeper のみ採用）。応答時間短縮のため頭数を抑制。
    sleepers_res = await find_sleepers(session, race_id_str, min_fav=min_fav, max_horses=10)
    sleeper_posts = [
        e["post_position"] for e in (sleepers_res or {}).get("entries", [])
        if e.get("is_sleeper") and e.get("post_position")
    ]

    honmei = ranked[:6]
    honmei_budget = max(0, round(budget * honmei_ratio / 100) * 100)
    ana_budget = budget - honmei_budget

    h_ja, a_ja = BET_JA.get(honmei_bet, honmei_bet), BET_JA.get(ana_bet, ana_bet)
    menu: list[dict] = []

    # 本命サイド
    h_combos = _honmei_combos(honmei_bet, honmei)
    if h_combos and honmei_budget >= 100:
        menu.append({
            "bet": honmei_bet, "method": "hedge", "combos": h_combos,
            "axis": [ranked[0]] if honmei_bet in ("trio", "trifecta", "umatan") else None,
            "horses": honmei[:6],
            "rationale": f"本命サイド: 人気上位の{h_ja}(順当決着を回収)",
            "weight": 2, "budget": honmei_budget,
        })

    coverage = f"人気で決着→{h_ja} / 穴が来る→穴{a_ja}、で相互カバー。"
    if sleeper_posts:
        partners = [p for p in honmei if p not in sleeper_posts] + list(sleeper_posts)
        a_combos = _ana_combos(ana_bet, sleeper_posts, partners)
        if a_combos and ana_budget >= 100:
            menu.append({
                "bet": ana_bet, "method": "hedge", "combos": a_combos,
                "horses": _uniq(list(sleeper_posts) + partners)[:8],
                "rationale": f"穴サイド: 穴×上位/他穴の{a_ja}(一発を拾う)",
                "weight": 1, "budget": ana_budget,
            })
    else:
        coverage = f"穴候補が検出されなかったため、本命の{h_ja}のみ。"
        if menu:
            menu[0]["budget"] = budget  # 全額を本命サイドへ

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
