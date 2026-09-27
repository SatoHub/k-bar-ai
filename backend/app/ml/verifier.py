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

# 🔴 **損益分岐は ROI 1.0。** ROI = 払戻合計 / 賭け金合計 なので、
#    1.0 を下回っている限り賭け続けるほど確実に減る。
BREAKEVEN_ROI = 1.0

# JRA の単勝払戻率（控除率20%）。**無技能で賭け続けた期待 ROI** がこの値。
# ⚠️ これは「損益分岐」ではない。0.85 なら市場平均は超えているが、
#    100円あたり15円ずつ減り続ける。参考線として使うだけにすること
#    （当初 breakeven と誤称しており、レビュー3件で同一指摘を受けた）。
RANDOM_BET_EXPECTED_ROI = 0.80

# 単勝 ROI は高オッズ1本で大きく動く。これ未満の件数ではフラグを信用しない。
MIN_BETS_FOR_RELIABLE_ROI = 500

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
    # actual_position の NaN 除外は呼び出し側でも行っているが、金銭の計算なので
    # ここでも防御する（未確定レースを「ハズレ」として分母に入れないため）。
    usable = bets[
        bets["win_odds"].notna()
        & (bets["win_odds"] > 0)
        & bets["actual_position"].notna()
    ]
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

    # 🔴 未確定（着順が入っていない）レースを除外する。
    #    prediction_logs にはこれから走るレースの予想も入り、win_odds は
    #    オッズ取得ジョブが結果より先に埋める。除外しないと
    #    「賭け金は計上されるが払戻ゼロ」= 全部ハズレとして集計され、
    #    的中率も ROI も過小になる（codex レビューで検出）。
    #    `NULL <= 3` は False になるため的中率も同じ影響を受けていた。
    pending = int(df["actual_position"].isna().sum())
    df = df[df["actual_position"].notna()]
    if df.empty:
        logger.warning(
            "version '%s' の予想 %d 件はすべて未確定レース（集計対象なし）",
            version,
            total,
        )
        return {
            "version": version,
            "total_predictions": total,
            "settled_predictions": 0,
            "pending_predictions": pending,
        }
    if pending:
        logger.info("未確定レースの予想 %d 件を集計から除外した", pending)

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
    # ⚠️ netkeiba はオッズ同値の馬に**同じ人気番号**を振るため、
    #    `win_favorite == 1` は1レース複数頭になり得る（このリポジトリの
    #    upset_score.py も `(g["win_favorite"] == 1).sum() != 1` でタイを
    #    除外しており、発生を前提にしている）。レース単位で1頭に落とす。
    favorites = (
        df[df["win_favorite"] == 1]
        .sort_values(["race_id_str", "win_odds", "predicted_position"])
        .groupby("race_id_str", as_index=False)
        .head(1)
    )
    fav_roi = _win_roi(favorites)

    summary = {
        "version": version,
        "total_predictions": total,
        "settled_predictions": int(len(df)),
        "pending_predictions": pending,
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
        # 🔴 実際に増えるかどうかはこれだけが答え（ROI > 1.0）
        "breakeven_roi": BREAKEVEN_ROI,
        "is_profitable": (ai_roi["roi"] is not None and ai_roi["roi"] > BREAKEVEN_ROI),
        # 参考線: 無技能で賭け続けた期待値（控除率由来）。超えても赤字は赤字
        "random_bet_expected_roi": RANDOM_BET_EXPECTED_ROI,
        "beats_random_bet": (
            ai_roi["roi"] is not None and ai_roi["roi"] > RANDOM_BET_EXPECTED_ROI
        ),
        "beats_favorite": (
            ai_roi["roi"] is not None
            and fav_roi["roi"] is not None
            and ai_roi["roi"] > fav_roi["roi"]
        ),
        # 🔴 件数が少ないと ROI は高オッズ1本で大きく動く。フラグを鵜呑みにしないこと
        "roi_sample_is_small": ai_roi["bets"] < MIN_BETS_FOR_RELIABLE_ROI,
        "min_bets_for_reliable_roi": MIN_BETS_FOR_RELIABLE_ROI,
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
        "  単勝ROI: AI◎=%s (%d点) / 1番人気=%s"
        " → 黒字(>100%%)=%s / 無技能(80%%)超え=%s / 市場超え=%s%s",
        f"{ai_roi['roi']:.1%}" if ai_roi["roi"] is not None else "N/A",
        ai_roi["bets"],
        f"{fav_roi['roi']:.1%}" if fav_roi["roi"] is not None else "N/A",
        summary["is_profitable"],
        summary["beats_random_bet"],
        summary["beats_favorite"],
        f"（⚠️ {MIN_BETS_FOR_RELIABLE_ROI}点未満なのでROIは不安定）"
        if summary["roi_sample_is_small"]
        else "",
    )
    if summary["beats_random_bet"] and not summary["is_profitable"]:
        logger.warning(
            "  ⚠️ 無技能の期待値(80%%)は超えているが ROI は100%%未満。"
            "賭け続ければ減る。「市場に勝った」と「儲かる」は別。"
        )

    return summary
