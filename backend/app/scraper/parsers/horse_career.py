"""Parse a horse's full career results from db.netkeiba.com/horse/result/{id}.

This gives the COMPLETE past form (incl. races not in our own DB), so we can
compute surface-split ability and spot "巻き返し穴" — e.g. a graded turf winner
whose last run was a dirt flop (→ low popularity) returning to turf today.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# ヘッダー名 → 取りたいキー
_WANT = {
    "日付": "date",
    "レース名": "race_name",
    "頭数": "field_size",
    "人気": "win_favorite",
    "着順": "finish_position",
    "距離": "surface_distance",  # 例 "芝1800" / "ダ1800" / "障3000"
}

_SURFACE_MAP = {"芝": "芝", "ダ": "ダート", "障": "障害"}
_GRADE_RE = re.compile(r"\((G[I1-3]+|L|OP|G)\)|\((重賞)\)")


def _to_int(s: str) -> int | None:
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None


def parse_horse_career(html: str) -> list[dict]:
    """Return a list of past runs (newest first), each:
    {date, race_name, grade, surface, distance_m, finish_position,
     field_size, win_favorite}.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.db_h_race_results")
    if not table:
        return []

    rows = table.select("tr")
    if len(rows) < 2:
        return []

    headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    idx = {label: i for i, label in enumerate(headers)}
    # 必要な列が揃わなければ諦める
    if "距離" not in idx or "着順" not in idx:
        return []

    def cell(tds, label):
        i = idx.get(label)
        return tds[i].get_text(strip=True) if i is not None and i < len(tds) else ""

    runs: list[dict] = []
    for row in rows[1:]:
        tds = row.find_all("td")
        if not tds:
            continue
        sd = cell(tds, "距離")  # "芝1800"
        surface = _SURFACE_MAP.get(sd[:1]) if sd else None
        distance_m = _to_int(sd)
        finish = _to_int(cell(tds, "着順"))
        if surface is None or finish is None:
            continue  # 出走取消・除外などはスキップ
        race_name = cell(tds, "レース名")
        gm = _GRADE_RE.search(race_name)
        grade = gm.group(1) if gm else None
        runs.append(
            {
                "date": cell(tds, "日付"),
                "race_name": race_name,
                "grade": grade,  # "GIII" / "L" / "OP" / None
                "surface": surface,
                "distance_m": distance_m,
                "finish_position": finish,
                "field_size": _to_int(cell(tds, "頭数")),
                "win_favorite": _to_int(cell(tds, "人気")),
            }
        )
    return runs
