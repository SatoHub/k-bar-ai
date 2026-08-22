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
    "tansho": "単勝",
    "fukusho": "複勝",
    "umaren": "馬連",
    "wide": "ワイド",
    "umatan": "馬単",
    "trio": "三連複",
    "trifecta": "三連単",
}


def _uniq(seq):
    return list(dict.fromkeys(seq))


# 荒れ度ごとの「広さ」: (対抗の頭数, 穴の頭数)。highほど穴まで広げる。
_WIDTH = {"low": (2, 1), "mid": (2, 2), "high": (3, 3)}


def _spectrum_combos(
    bet: str, honmei: list[int], ana_pool: list[int], level: str
) -> tuple[list[tuple], dict]:
    """メイン: 本命2頭を「マルチ軸」にした統合フォーメーション。

    本命2頭のどちらか1頭でも上位に来れば的中しうる広いカバー。相手は対抗
    (本命3位以降)＋穴で、荒れ度で本数を可変(_WIDTH)。これ一本で
    順当(本命3)・中間(本命2+穴1)・やや波乱(本命1+穴2)を連続カバーする。

    Returns: (combos, meta)。meta={axis, others, universe} を表示用に返す。
    """
    if len(honmei) < 1:
        return [], {}
    axis = honmei[:2]  # 本命2頭(マルチ軸)。1頭しか無ければ1頭軸。
    n_taikou, n_ana = _WIDTH.get(level, (2, 2))
    others = _uniq(honmei[2 : 2 + n_taikou] + ana_pool[:n_ana])
    universe = _uniq(axis + others)
    axset = set(axis)
    meta = {"axis": axis, "others": others, "universe": universe}

    def ok(c):  # 軸(本命2頭)のどれかを含む組だけ採用
        return any(p in axset for p in c)

    if bet == "trio" and len(universe) >= 3:
        return _uniq(
            [tuple(sorted(c)) for c in combinations(universe, 3) if ok(c)]
        ), meta
    if bet == "trifecta" and len(universe) >= 3:
        res = []
        for c in combinations(universe, 3):
            if ok(c):
                res += list(permutations(c))
        return _uniq(res), meta
    if bet in ("wide", "umaren") and len(universe) >= 2:
        return _uniq(
            [tuple(sorted(c)) for c in combinations(universe, 2) if ok(c)]
        ), meta
    if bet == "umatan" and len(universe) >= 2:
        res = []
        for c in combinations(universe, 2):
            if ok(c):
                res += [c, (c[1], c[0])]
        return _uniq(res), meta
    if bet in ("tansho", "fukusho"):
        return [(a,) for a in axis], meta
    return [], meta


def _insurance_combos(bet: str, ana_pool: list[int]) -> list[tuple]:
    """保険: 穴3頭だけの大波乱(本命総崩れ)カバー。荒れ度highのときに薄く張る。"""
    p = ana_pool
    if len(p) < 1:
        return []
    if bet == "trio" and len(p) >= 3:
        return _uniq([tuple(sorted(c)) for c in combinations(p[:3], 3)])
    if bet == "trifecta" and len(p) >= 3:
        res = []
        for c in combinations(p[:3], 3):
            res += list(permutations(c))
        return _uniq(res)
    if bet in ("wide", "umaren") and len(p) >= 2:
        return _uniq([tuple(sorted(c)) for c in combinations(p[:3], 2)])
    if bet == "umatan" and len(p) >= 2:
        res = []
        for c in combinations(p[:3], 2):
            res += [c, (c[1], c[0])]
        return _uniq(res)
    if bet in ("tansho", "fukusho"):
        return [(p[0],)]
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
            horses.append(
                {
                    "post": e.post_position,
                    "win_odds": float(e.win_odds),
                    "win_favorite": e.win_favorite,
                }
            )

    ranked_pairs = [
        (p["predicted_position"], post_by_horse.get(p["horse_id"]))
        for p in predictions
        if p.get("predicted_position") and post_by_horse.get(p["horse_id"])
    ]
    ranked = [post for _, post in sorted(ranked_pairs)]

    base = {
        "race_id": race_id_str,
        "race_name": race.race_name,
        "budget": budget,
        "alloc_mode": "gami_avoid",
        "upset_level": level,
        "names": {str(k): v for k, v in names.items()},
    }
    if not horses or len(ranked) < 4:
        return {
            **base,
            "odds_live": False,
            "total_allocated": 0,
            "suggestions": [],
            "message": "予想またはオッズが不足しています",
        }

    # 穴馬を検出（応答時間短縮のため頭数を抑制）
    sleepers_res = await find_sleepers(
        session, race_id_str, min_fav=min_fav, max_horses=10
    )
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
    for h in sorted(horses, key=lambda x: x.get("win_favorite") or 99):
        p = h["post"]
        if (
            (h.get("win_favorite") or 99) >= min_fav
            and p not in honmei_set
            and p not in ana_pool
        ):
            ana_pool.append(p)
    ana_pool = ana_pool[:5]

    honmei_budget = max(0, round(budget * honmei_ratio / 100) * 100)
    ana_budget = budget - honmei_budget
    h_ja, a_ja = BET_JA.get(honmei_bet, honmei_bet), BET_JA.get(ana_bet, ana_bet)
    menu: list[dict] = []

    # メイン: 本命2頭マルチ軸の統合フォーメーション(順当〜やや波乱を連続カバー)
    h_combos, meta = _spectrum_combos(honmei_bet, honmei, ana_pool, level)
    main_axis = meta.get("axis") or [honmei[0]]
    if h_combos and honmei_budget >= 100:
        menu.append(
            {
                "bet": honmei_bet,
                "method": "hedge",
                "combos": h_combos,
                "axis": None if honmei_bet in ("tansho", "fukusho") else main_axis,
                "horses": meta.get("universe") or honmei,
                "rationale": (
                    f"メイン: 本命2頭マルチ軸の{h_ja}フォーメーション"
                    "(本命のどちらか1頭絡みで順当〜やや波乱を広くカバー)"
                ),
                "weight": 2,
                "budget": honmei_budget,
            }
        )

    # 保険: 穴3頭の大波乱(本命総崩れ)カバー。荒れ度highのときだけ張る。
    a_combos = _insurance_combos(ana_bet, ana_pool) if level == "high" else []
    if a_combos and ana_budget >= 100 and menu:
        menu.append(
            {
                "bet": ana_bet,
                "method": "hedge",
                "combos": a_combos,
                "axis": [ana_pool[0]]
                if ana_bet in ("trio", "trifecta", "umatan")
                else None,
                "horses": ana_pool[:3],
                "rationale": f"保険: 穴{a_ja}(本命総崩れの大波乱に備える)",
                "weight": 1,
                "budget": ana_budget,
            }
        )
        coverage = (
            f"本命2頭軸の{h_ja}で順当〜やや波乱を広くカバー＋穴{a_ja}で大波乱に保険。"
        )
    elif menu:
        menu[0]["budget"] = budget  # 保険なし → 全額メインへ
        coverage = f"本命2頭軸の{h_ja}フォーメーションで順当〜やや波乱を広くカバー" + (
            "（荒れ度highなら穴保険も追加）。" if level != "high" else "。"
        )

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
                            k: v["odds"]
                            for k, v in parsed["combos"].items()
                            if v.get("odds")
                        }
                except Exception as e:  # noqa: BLE001
                    logger.warning("hedge odds fetch failed %s: %s", t, e)
    except Exception as e:  # noqa: BLE001
        logger.warning("hedge odds scraper failed: %s", e)

    res = suggest(
        budget,
        horses,
        ranked,
        level,
        odds_lookup=odds_lookup or None,
        alloc_mode="gami_avoid",
        menu_override=menu,
    )
    res.update(base)
    res["odds_live"] = bool(odds_lookup)
    res["coverage_note"] = coverage
    res["sleeper_posts"] = sleeper_posts
    return res
