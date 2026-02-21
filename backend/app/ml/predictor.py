"""
Race prediction with SHAP-based Japanese explanations.

Loads a trained model, predicts for a given race or date, generates
human-readable Japanese explanations using SHAP feature contributions,
and saves results to the prediction_logs table.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

import joblib
import numpy as np
import pandas as pd
import shap
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.config import (
    FEATURE_LABEL_JA,
    MODELS_DIR,
    TOP_SHAP_FEATURES,
)
from app.ml.features import build_feature_matrix
from app.models import ModelVersion, PredictionLog

logger = logging.getLogger(__name__)


def _load_model(version: str) -> dict:
    """Load a model artifact from disk."""
    model_path = MODELS_DIR / f"{version}.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    return joblib.load(model_path)


def _generate_explanation(
    shap_values: np.ndarray,
    feature_names: list[str],
    feature_row: pd.Series,
    top_n: int = TOP_SHAP_FEATURES,
) -> str:
    """
    Generate a Japanese explanation from SHAP values for a single prediction.

    Returns a string like:
    "この馬の予想根拠: 騎手の通算勝率が高い(+0.12)、直近3走の平均着順が良い(+0.08)..."
    """
    abs_shap = np.abs(shap_values)
    top_indices = np.argsort(abs_shap)[::-1][:top_n]

    reasons = []
    for idx in top_indices:
        feat_name = feature_names[idx]
        shap_val = shap_values[idx]
        feat_val = feature_row.iloc[idx]

        ja_label = FEATURE_LABEL_JA.get(feat_name, feat_name)

        if shap_val > 0:
            direction = "高い" if isinstance(feat_val, (int, float)) else "プラス"
            reasons.append(f"{ja_label}が{direction}({shap_val:+.3f})")
        else:
            direction = "低い" if isinstance(feat_val, (int, float)) else "マイナス"
            reasons.append(f"{ja_label}が{direction}({shap_val:+.3f})")

    return "この馬の予想根拠: " + "、".join(reasons)


def predict_race(
    version: str,
    race_id_str: str | None = None,
    target_date: date | None = None,
    save_to_db: bool = True,
) -> list[dict]:
    """
    Generate predictions for a specific race or all races on a date.

    Args:
        version: Model version string (e.g. "v1.0.0")
        race_id_str: Specific race_id to predict (optional)
        target_date: Date to predict all races for (optional)
        save_to_db: Whether to save predictions to prediction_logs

    Returns:
        List of prediction dicts grouped by race.
    """
    artifact = _load_model(version)
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]

    # Build feature matrix for prediction targets (include upcoming races)
    logger.info("Building feature matrix for prediction...")
    df = build_feature_matrix(include_upcoming=True)

    # Filter to target
    if race_id_str:
        df = df[df["race_id_str"] == race_id_str]
    elif target_date:
        df = df[df["race_date"].dt.date == target_date]
    else:
        raise ValueError("Either race_id_str or target_date must be specified")

    if df.empty:
        logger.warning("No data found for the specified filter")
        return []

    # Predict
    X = df[feature_columns].copy()
    y_prob = model.predict(X)

    # SHAP explanations
    logger.info("Computing SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    # Build results
    results = []
    engine = create_engine(settings.database_url_sync) if save_to_db else None

    # Get model_version UUID
    model_version_uuid = None
    if save_to_db:
        with Session(engine) as session:
            mv = session.execute(
                select(ModelVersion).where(ModelVersion.version == version)
            ).scalar_one_or_none()
            if mv:
                model_version_uuid = mv.id

    for i, (idx, row) in enumerate(df.iterrows()):
        score = float(y_prob[i])
        explanation = _generate_explanation(
            shap_values[i],
            feature_columns,
            X.iloc[i],
        )

        # Confidence label
        if score >= 0.7:
            confidence = "high"
        elif score >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        result = {
            "race_id_str": row["race_id_str"],
            "race_date": row["race_date"],
            "racecourse_name": row.get("racecourse_name", ""),
            "horse_name": row.get("horse_name", ""),
            "horse_uuid": row["horse_uuid"],
            "race_uuid": row["race_uuid"],
            "score": score,
            "confidence": confidence,
            "explanation": explanation,
            "actual_finish": row.get("finish_position"),
        }
        results.append(result)

    # Sort by race, then score descending
    results.sort(key=lambda r: (r["race_id_str"], -r["score"]))

    # Assign predicted_position per race
    current_race = None
    pos = 0
    for r in results:
        if r["race_id_str"] != current_race:
            current_race = r["race_id_str"]
            pos = 0
        pos += 1
        r["predicted_position"] = pos

    # Save to DB
    if save_to_db and engine is not None:
        _save_predictions(engine, results, model_version_uuid)

    if engine is not None:
        engine.dispose()

    return results


def _save_predictions(
    engine,
    results: list[dict],
    model_version_uuid: uuid.UUID | None,
) -> None:
    """Bulk-insert predictions into prediction_logs."""
    with Session(engine) as session:
        rows = []
        for r in results:
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "race_id": r["race_uuid"],
                    "horse_id": r["horse_uuid"],
                    "model_version_id": model_version_uuid,
                    "predicted_position": r["predicted_position"],
                    "predicted_score": r["score"],
                    "explanation": r["explanation"],
                    "confidence": r["confidence"],
                }
            )

        if rows:
            stmt = pg_insert(PredictionLog.__table__).values(rows)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)
            session.commit()
            logger.info("Saved %d predictions to DB", len(rows))
