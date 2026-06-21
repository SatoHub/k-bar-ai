"""Unit tests for 巻き返し穴(sleeper) detection (pure, no network)."""

import datetime

from app.services.sleeper import compute_sleeper

RACE_DATE = datetime.date(2026, 6, 21)


def _run(date, surface, finish, fav=5, fs=16, grade=None):
    return {
        "date": date, "surface": surface, "distance_m": 1800,
        "finish_position": finish, "field_size": fs, "win_favorite": fav,
        "grade": grade, "race_name": "X",
    }


def test_surface_switch_sleeper_flagged():
    # 芝の重賞実績馬が前走ダートで大敗→14人気 = ミアネーロ型
    career = [
        _run("2026/03/08", "ダート", 15, fav=11, fs=16),       # 前走ダート大敗
        _run("2025/09/07", "芝", 2, fav=3, grade="GII"),       # 芝重賞2着
        _run("2025/05/19", "芝", 1, fav=1, grade="GIII"),      # 芝重賞勝ち
        _run("2025/03/01", "芝", 4, fav=5),
    ]
    s = compute_sleeper("芝", 14, career, before_date=RACE_DATE)
    assert s["is_sleeper"] is True
    assert s["surface_mismatch"] is True
    assert s["has_win"] is True
    assert s["score"] >= 0.6
    assert "条件替わり" in s["reason"]


def test_good_but_no_mismatch_not_flagged():
    # 芝実績はあるが前走も芝(条件替わりなし) → 🔴では旗立てない
    career = [
        _run("2026/03/08", "芝", 5, fav=6),
        _run("2025/09/07", "芝", 2, fav=3, grade="GIII"),
        _run("2025/05/19", "芝", 3, fav=4),
        _run("2025/03/01", "芝", 1, fav=2),
    ]
    s = compute_sleeper("芝", 8, career, before_date=RACE_DATE)
    assert s["is_sleeper"] is False  # 条件替わりの理由がない


def test_no_surface_history():
    # 今走芝だが過去ダートのみ → sleeperにならない
    career = [_run("2026/03/08", "ダート", 3), _run("2025/12/01", "ダート", 1)]
    s = compute_sleeper("芝", 10, career, before_date=RACE_DATE)
    assert s["is_sleeper"] is False
    assert s["surface_runs"] == 0


def test_before_date_excludes_target_race():
    # 当日のレース結果はキャリアから除外(リーク防止)
    career = [
        _run("2026/06/21", "芝", 3, fav=14),  # 当日(除外されるべき)
        _run("2026/03/08", "ダート", 15, fav=11),
        _run("2025/09/07", "芝", 2, grade="GII"),
        _run("2025/05/19", "芝", 1, grade="GIII"),
    ]
    s = compute_sleeper("芝", 14, career, before_date=RACE_DATE)
    # 当日を除いた前走はダート大敗のはず → mismatch成立
    assert s["surface_mismatch"] is True
    assert s["is_sleeper"] is True
