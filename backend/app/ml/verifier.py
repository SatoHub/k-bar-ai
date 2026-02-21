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

_VERIFY_SQL = text("""
    SELECT
        pl.id AS prediction_id,
        pl.predicted_position,
        pl.predicted_score,
        pl.confidence,
        re.finish_position AS actual_position,
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

    return summary
