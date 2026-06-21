"""巻き返し穴（sleeper）検出。

今走と同じ馬場(芝/ダート)でのキャリア実力と、市場人気の乖離から、
「前走の凡走（別馬場など）で人気を落としているが、今日の条件なら走る馬」を炙り出す。
府中牝馬Sのミアネーロ（芝の重賞実績馬が前走ダート大敗→14人気→3着）が典型。

純粋関数。career_runs は netkeiba 全成績パーサーの出力(新しい順)。
"""

from __future__ import annotations

import datetime

_GRADED = {"GI", "GII", "GIII", "G", "L", "OP", "重賞"}


def _parse_date(s: str) -> datetime.date | None:
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def compute_sleeper(
    today_surface: str | None,
    win_favorite: int | None,
    career_runs: list[dict],
    before_date: datetime.date | None = None,
) -> dict:
    """今走の馬場での実力と人気の歪みから sleeper 度を算出。

    Returns dict(is_sleeper, score, reason, surface, surface_runs,
                 surface_places, surface_place_rate, has_win, graded_good,
                 surface_mismatch).
    """
    # 当日以降のレースは除外（リーク防止）
    runs = career_runs
    if before_date is not None:
        runs = [r for r in runs if (d := _parse_date(r.get("date", ""))) and d < before_date]

    blank = {
        "is_sleeper": False, "score": 0.0, "reason": "", "surface": today_surface,
        "surface_runs": 0, "surface_places": 0, "surface_place_rate": 0.0,
        "has_win": False, "graded_good": False, "surface_mismatch": False,
    }
    if not today_surface or not runs:
        return blank

    same = [r for r in runs if r.get("surface") == today_surface and r.get("finish_position")]
    n = len(same)
    if n == 0:
        return {**blank, "reason": f"{today_surface}での出走歴なし"}

    places = sum(1 for r in same if r["finish_position"] <= 3)
    wins = sum(1 for r in same if r["finish_position"] == 1)
    place_rate = places / n
    has_win = wins > 0
    graded_good = any(
        (r.get("grade") in _GRADED) and r["finish_position"] <= 3 for r in same
    )

    last = runs[0]
    surface_mismatch = last.get("surface") != today_surface
    fs = last.get("field_size")
    recent_poor = bool(
        last.get("finish_position") and fs and last["finish_position"] > fs * 0.6
    )
    unpopular = (win_favorite or 99) >= 6

    # 今走馬場での実力
    ability = min(1.0, place_rate + (0.2 if has_win else 0.0) + (0.25 if graded_good else 0.0))

    # sleeper度: 「前走が別馬場で大敗→人気急落」した今走馬場の実力馬を最優先で炙り出す。
    # （重賞では人気薄でも全馬が相応の実績を持つため、"人気薄かつ好成績"だけでは選別不可。
    #   "不当に人気を落とした理由(条件替わり)がある"ことを主信号にする）
    score = 0.0
    primary = surface_mismatch and recent_poor and unpopular and n >= 2 and ability >= 0.3
    if primary:
        score = min(1.0, 0.6 + ability * 0.4)  # 巻き返し穴の本命パターン
    elif unpopular and n >= 3 and ability >= 0.55 and (has_win or graded_good):
        score = round(ability * 0.5, 3)  # 条件替わりは無いが実績抜群の人気薄(控えめ評価)

    # 説明文
    bits = [f"{today_surface}で複勝率{place_rate:.0%}({places}/{n})"]
    if has_win:
        bits.append("勝ち鞍あり")
    if graded_good:
        bits.append("重賞/OPで好走歴")
    if surface_mismatch and recent_poor:
        bits.append(f"★前走は{last.get('surface')}で大敗→人気急落(条件替わり)")
    elif surface_mismatch:
        bits.append(f"前走は{last.get('surface')}")
    reason = "・".join(bits)

    return {
        "is_sleeper": score >= 0.6,  # 主に「条件替わりで人気急落の実力馬」を旗立て
        "score": round(score, 3),
        "reason": reason,
        "surface": today_surface,
        "surface_runs": n,
        "surface_places": places,
        "surface_place_rate": round(place_rate, 3),
        "has_win": has_win,
        "graded_good": graded_good,
        "surface_mismatch": surface_mismatch,
    }
