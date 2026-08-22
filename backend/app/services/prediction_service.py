"""Service layer for prediction-related queries (async)."""

from __future__ import annotations

import joblib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.ml.config import MODELS_DIR
from app.models import Horse, ModelVersion, PredictionLog, Race, RaceEntry


async def get_model_versions(session: AsyncSession) -> list[ModelVersion]:
    """List all model versions ordered by creation date descending."""
    result = await session.execute(
        select(ModelVersion).order_by(ModelVersion.created_at.desc())
    )
    return list(result.scalars().all())


async def get_model_metrics(session: AsyncSession, version: str) -> dict | None:
    """
    Get combined training + verification metrics for a model version.

    Training metrics come from the joblib artifact.
    """
    mv = await session.execute(
        select(ModelVersion).where(ModelVersion.version == version)
    )
    mv = mv.scalar_one_or_none()
    if not mv:
        return None

    # Load training metrics from artifact
    model_path = MODELS_DIR / f"{version}.joblib"
    metrics = {
        "version": version,
        "accuracy": mv.accuracy,
    }

    if model_path.exists():
        artifact = joblib.load(model_path)
        train_metrics = artifact.get("metrics", {})
        metrics.update(
            {
                "f1": train_metrics.get("f1"),
                "roc_auc": train_metrics.get("roc_auc"),
                "train_rows": train_metrics.get("train_rows"),
                "test_rows": train_metrics.get("test_rows"),
                "best_iteration": train_metrics.get("best_iteration"),
                "cutoff_year": artifact.get("cutoff_year"),
            }
        )

    return metrics


async def get_race_predictions(
    session: AsyncSession,
    race_id_str: str,
) -> dict | None:
    """
    Get predictions for a specific race.

    Returns predictions joined with horse names and actual finish positions.
    """
    # Get the race
    result = await session.execute(select(Race).where(Race.race_id == race_id_str))
    race = result.scalar_one_or_none()
    if not race:
        return None

    # Get predictions for this race
    result = await session.execute(
        select(PredictionLog)
        .where(PredictionLog.race_id == race.id)
        .distinct(PredictionLog.race_id, PredictionLog.horse_id)
        .order_by(
            PredictionLog.race_id,
            PredictionLog.horse_id,
            PredictionLog.predicted_score.desc(),
        )
    )
    predictions = sorted(
        result.scalars().all(),
        key=lambda p: p.predicted_score or 0,
        reverse=True,
    )

    if not predictions:
        return {
            "race_id": race_id_str,
            "race_date": race.race_date,
            "racecourse_name": race.racecourse_name,
            "race_name": race.race_name,
            "predictions": [],
        }

    # Get horse names and actual positions
    horse_ids = [p.horse_id for p in predictions]
    result = await session.execute(select(Horse).where(Horse.id.in_(horse_ids)))
    horses = {h.id: h for h in result.scalars().all()}

    # Get actual finish positions
    result = await session.execute(
        select(RaceEntry).where(
            RaceEntry.race_id == race.id,
            RaceEntry.horse_id.in_(horse_ids),
        )
    )
    entries = {e.horse_id: e for e in result.scalars().all()}

    # Get model version name
    model_version_str = None
    if predictions and predictions[0].model_version_id:
        result = await session.execute(
            select(ModelVersion).where(
                ModelVersion.id == predictions[0].model_version_id
            )
        )
        mv = result.scalar_one_or_none()
        if mv:
            model_version_str = mv.version

    pred_entries = []
    upset_inputs = []
    for p in predictions:
        horse = horses.get(p.horse_id)
        entry = entries.get(p.horse_id)
        pred_entries.append(
            {
                "id": p.id,
                "horse_id": p.horse_id,
                "horse_name": horse.name if horse else None,
                "predicted_position": p.predicted_position,
                "predicted_score": p.predicted_score,
                "confidence": p.confidence,
                "explanation": p.explanation,
                "actual_finish": entry.finish_position if entry else None,
                "shap_data": p.shap_data,
            }
        )
        if entry is not None:
            upset_inputs.append(
                {
                    "win_odds": float(entry.win_odds)
                    if entry.win_odds is not None
                    else None,
                    "win_favorite": entry.win_favorite,
                    "predicted_score": p.predicted_score,
                }
            )

    # 荒れ度スコア (race-level) — 算出失敗時は None
    from app.ml.upset_score import score_race

    try:
        upset = score_race(upset_inputs)
    except Exception:  # 推論失敗で予想全体を落とさない
        upset = None

    return {
        "race_id": race_id_str,
        "race_date": race.race_date,
        "racecourse_name": race.racecourse_name,
        "race_name": race.race_name,
        "model_version": model_version_str,
        "upset": upset,
        "predictions": pred_entries,
    }
