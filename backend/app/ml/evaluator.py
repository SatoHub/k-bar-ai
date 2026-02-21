"""
Model evaluation summary display.

Loads model artifacts and verification results to produce
a human-readable performance report.
"""

from __future__ import annotations

import logging

import joblib

from app.ml.config import MODELS_DIR
from app.ml.verifier import verify_predictions

logger = logging.getLogger(__name__)


def evaluate_model(version: str) -> str:
    """
    Generate a comprehensive evaluation report for a model version.

    Returns a formatted string report.
    """
    # Load model artifact for training metrics
    model_path = MODELS_DIR / f"{version}.joblib"
    if not model_path.exists():
        return f"Error: Model artifact not found at {model_path}"

    artifact = joblib.load(model_path)
    train_metrics = artifact.get("metrics", {})

    # Get verification results
    verify_results = verify_predictions(version)

    lines = [
        f"=== Model Evaluation: {version} ===",
        "",
        "--- Training Metrics ---",
        f"  Accuracy:       {train_metrics.get('accuracy', 'N/A'):.4f}"
        if isinstance(train_metrics.get("accuracy"), float)
        else "  Accuracy:       N/A",
        f"  F1 Score:       {train_metrics.get('f1', 'N/A'):.4f}"
        if isinstance(train_metrics.get("f1"), float)
        else "  F1 Score:       N/A",
        f"  ROC AUC:        {train_metrics.get('roc_auc', 'N/A'):.4f}"
        if isinstance(train_metrics.get("roc_auc"), float)
        else "  ROC AUC:        N/A",
        f"  Train rows:     {train_metrics.get('train_rows', 'N/A')}",
        f"  Test rows:      {train_metrics.get('test_rows', 'N/A')}",
        f"  Best iteration: {train_metrics.get('best_iteration', 'N/A')}",
        f"  Cutoff year:    {artifact.get('cutoff_year', 'N/A')}",
        "",
    ]

    if verify_results.get("total_predictions", 0) > 0:
        lines.extend(
            [
                "--- Prediction Verification ---",
                f"  Races verified:   {verify_results['unique_races']}",
                f"  Total predictions: {verify_results['total_predictions']}",
                f"  Win hit rate:     {verify_results['win_hit_rate']:.1%} ({verify_results['win_hits']}/{verify_results['win_attempts']})",
                f"  Place hit rate:   {verify_results['place_hit_rate']:.1%} ({verify_results['place_hits']}/{verify_results['place_attempts']})",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "--- Prediction Verification ---",
                "  No predictions found. Run 'predict' first.",
                "",
            ]
        )

    lines.append("=" * 40)
    return "\n".join(lines)
