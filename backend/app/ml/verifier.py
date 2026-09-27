"""
Prediction verification: compare predictions vs actual race results.

Queries prediction_logs and joins with race_entries to compute
hit rates for win (1st) and place (top 3).
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)

# 単勝1点あたりの賭け金（円）。ROI は「払戻合計 / 賭け金合計」。
BET_UNIT_YEN = 100

# JRA の単勝払戻率。控除率20%なので、無技能で賭け続けた期待 ROI は約 0.80。
# **この値を超えていなければ、そのモデルに賭ける意味は無い。**
JRA_WIN_PAYOUT_RATE = 0.80

_VERIFY_SQL = text("""
    SELECT
        pl.id AS prediction_id,
        pl.predicted_position,
        pl.predicted_score,
        pl.confidence,
        re.finish_position AS actual_position,
        re.win_odds AS win_odds,
        re.win_favorite AS win_favorite,
        r.race_id AS race_id_str,
        r.race_date,
        h.name AS horse_name,
        mv.version AS model_version
    FROM prediction_logs pl
    JOIN races r ON r.id = pl.race_id
    JOIN horses h ON h.id = pl.horse_id
    JOIN race_entries re ON re.race_id = pl.race_id AND re.horse_id = pl.horse_id
    LEFT JOIN model_versions mv ON mv.id = pl.model_version_id
    WHERE mv.version = :version
    ORDER BY r.race_date, r.race_id, pl.predicted_position
""")


def _win_roi(bets: pd.DataFrame) -> dict:
    """
    単勝の ROI（払戻合計 / 賭け金合計）を計算する。

    **賭けられる条件について**:
      使う `win_odds` は結果ページから取得した「発走時の確定単勝オッズ」。
      これは着順には依存せず**発走前に市場で決まる値**なので、締切時点で
      観測できる情報のみで計算していることになる。ただし人間が数分前に
      見るオッズとはわずかにずれるため、ここで出る ROI は
      「締切直前に賭けた場合」の値として読むこと。
      オッズが欠損している行は賭けられないので集計から除外する。
    """
    usable = bets[bets["win_odds"].notna() & (bets["win_odds"] > 0)]
    skipped = int(len(bets) - len(usable))
    if usable.empty:
        return {"roi": None, "stake": 0, "payout": 0, "bets": 0, "skipped": skipped}

    stake = len(usable) * BET_UNIT_YEN
    won = usable[usable["actual_position"] == 1]
    payout = float((won["win_odds"].astype(float) * BET_UNIT_YEN).sum())
    return {
        "roi": float(payout / stake),
        "stake": int(stake),
        "payout": int(round(payout)),
        "bets": int(len(usable)),
        "skipped": skipped,
    }


def verify_predictions(version: str) -> dict:
    """
    Compare predictions for a model version against actual results.

    Returns a summary dict with hit rates and detailed results.
    """
    engine = create_engine(settings.database_url_sync)
    df = pd.read_sql(_VERIFY_SQL, engine, params={"version": version})
    engine.dispose()

    if df.empty:
        logger.warning("No predictions found for version '%s'", version)
        return {"version": version, "total_predictions": 0}

    total = len(df)

    # Place hit: predicted_position <= 3 AND actual_position <= 3
    top3_predictions = df[df["predicted_position"] <= 3]
    place_hits = top3_predictions[top3_predictions["actual_position"] <= 3]
    place_hit_rate = (
        len(place_hits) / len(top3_predictions) if len(top3_predictions) > 0 else 0.0
    )

    # Win hit: predicted_position == 1 AND actual_position == 1
    top1_predictions = df[df["predicted_position"] == 1]
    win_hits = top1_predictions[top1_predictions["actual_position"] == 1]
    win_hit_rate = (
        len(win_hits) / len(top1_predictions) if len(top1_predictions) > 0 else 0.0
    )

    # Top-3 accuracy: for predicted top 3, what fraction actually finished top 3
    top3_accuracy = place_hit_rate

    # Unique races
    unique_races = df["race_id_str"].nunique()

    # --- 単勝 ROI ---
    # AUC が上がっても ROI が上がらなければ目的（増えること）には効いていない。
    # そのため的中率と並べて必ず出す。
    ai_roi = _win_roi(top1_predictions)
    # 市場ベースライン: 毎レース1番人気に賭けた場合。
    # **AI がこれを超えられないなら、モデルは市場を再現しているだけ。**
    fav_roi = _win_roi(df[df["win_favorite"] == 1])

    summary = {
        "version": version,
        "total_predictions": total,
        "unique_races": unique_races,
        "win_hit_rate": float(win_hit_rate),
        "win_hits": int(len(win_hits)),
        "win_attempts": int(len(top1_predictions)),
        "place_hit_rate": float(place_hit_rate),
        "place_hits": int(len(place_hits)),
        "place_attempts": int(len(top3_predictions)),
        "top3_accuracy": float(top3_accuracy),
        # 単勝ROI（AI◎ = predicted_position==1 に毎レース BET_UNIT_YEN）
        "win_roi": ai_roi["roi"],
        "win_roi_stake_yen": ai_roi["stake"],
        "win_roi_payout_yen": ai_roi["payout"],
        "win_roi_bets": ai_roi["bets"],
        "win_roi_skipped_no_odds": ai_roi["skipped"],
        # 市場ベースライン（1番人気に毎レース）
        "favorite_roi": fav_roi["roi"],
        "favorite_roi_bets": fav_roi["bets"],
        # 控除率から来る「無技能の期待ROI」。これを超えていなければ賭ける意味は無い
        "breakeven_roi_vs_takeout": JRA_WIN_PAYOUT_RATE,
        "beats_takeout": (
            ai_roi["roi"] is not None and ai_roi["roi"] > JRA_WIN_PAYOUT_RATE
        ),
        "beats_favorite": (
            ai_roi["roi"] is not None
            and fav_roi["roi"] is not None
            and ai_roi["roi"] > fav_roi["roi"]
        ),
    }

    logger.info(
        "Verification for %s: %d races, win=%.1f%% (%d/%d), place=%.1f%% (%d/%d)",
        version,
        unique_races,
        win_hit_rate * 100,
        len(win_hits),
        len(top1_predictions),
        place_hit_rate * 100,
        len(place_hits),
        len(top3_predictions),
    )
    logger.info(
        "  単勝ROI: AI◎=%s / 1番人気=%s / 控除率の壁=%.0f%% "
        "→ 控除率超え=%s, 市場超え=%s",
        f"{ai_roi['roi']:.1%}" if ai_roi["roi"] is not None else "N/A",
        f"{fav_roi['roi']:.1%}" if fav_roi["roi"] is not None else "N/A",
        JRA_WIN_PAYOUT_RATE * 100,
        summary["beats_takeout"],
        summary["beats_favorite"],
    )

    return summary
