"""
LightGBM training pipeline.

Loads feature matrix, splits by time, trains LightGBM, saves model
artifact to disk, and registers version in model_versions table.
"""

from __future__ import annotations

import datetime
import logging
import uuid

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.config import (
    CATEGORICAL_COLUMNS,
    DEFAULT_CUTOFF_YEAR,
    FEATURE_COLUMNS,
    LGBM_EARLY_STOPPING_ROUNDS,
    LGBM_NUM_BOOST_ROUND,
    LGBM_PARAMS,
    MODELS_DIR,
    TARGET_COLUMN,
)
from app.ml.features import build_feature_matrix
from app.models.model_version import ModelVersion

logger = logging.getLogger(__name__)


def _split_by_time(
    df: pd.DataFrame,
    cutoff_year: int = DEFAULT_CUTOFF_YEAR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into train (< cutoff_year) and test (>= cutoff_year)."""
    train = df[df["race_date"].dt.year < cutoff_year].copy()
    test = df[df["race_date"].dt.year >= cutoff_year].copy()
    logger.info(
        "Train: %d rows (%d-%d), Test: %d rows (%d-%d)",
        len(train),
        train["race_date"].dt.year.min(),
        train["race_date"].dt.year.max(),
        len(test),
        test["race_date"].dt.year.min(),
        test["race_date"].dt.year.max(),
    )
    return train, test


def _prepare_lgb_dataset(
    df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract feature matrix X and target y from DataFrame."""
    all_features = FEATURE_COLUMNS + CATEGORICAL_COLUMNS
    X = df[all_features].copy()
    y = df[TARGET_COLUMN].values.astype(np.float64)
    return X, y


def train_model(
    version: str,
    cutoff_year: int = DEFAULT_CUTOFF_YEAR,
    description: str | None = None,
) -> dict:
    """
    Train a LightGBM model and save it.

    Returns a dict with evaluation metrics.
    """
    # 1. Build feature matrix
    logger.info("Building feature matrix...")
    df = build_feature_matrix()

    # 2. Time-series split
    train_df, test_df = _split_by_time(df, cutoff_year)

    # 3. Prepare datasets
    X_train, y_train = _prepare_lgb_dataset(train_df)
    X_test, y_test = _prepare_lgb_dataset(test_df)

    # 4. Validation split from train (last 10% by time)
    val_cutoff = int(len(X_train) * 0.9)
    X_val, y_val = X_train.iloc[val_cutoff:], y_train[val_cutoff:]
    X_train_final, y_train_final = X_train.iloc[:val_cutoff], y_train[:val_cutoff]

    cat_cols = [c for c in CATEGORICAL_COLUMNS if c in X_train.columns]

    train_set = lgb.Dataset(
        X_train_final,
        label=y_train_final,
        categorical_feature=cat_cols,
        free_raw_data=False,
    )
    val_set = lgb.Dataset(
        X_val,
        label=y_val,
        categorical_feature=cat_cols,
        free_raw_data=False,
        reference=train_set,
    )

    # 5. Train
    logger.info("Training LightGBM (num_boost_round=%d)...", LGBM_NUM_BOOST_ROUND)
    callbacks = [
        lgb.early_stopping(LGBM_EARLY_STOPPING_ROUNDS),
        lgb.log_evaluation(100),
    ]
    model = lgb.train(
        LGBM_PARAMS,
        train_set,
        num_boost_round=LGBM_NUM_BOOST_ROUND,
        valid_sets=[train_set, val_set],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    # 6. Evaluate on test set
    y_prob = model.predict(X_test)
    y_pred = (y_prob >= 0.5).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "test_rows": int(len(y_test)),
        "train_rows": int(len(y_train)),
        "best_iteration": model.best_iteration,
    }

    logger.info(
        "Test metrics: accuracy=%.4f, F1=%.4f, ROC-AUC=%.4f",
        metrics["accuracy"],
        metrics["f1"],
        metrics["roc_auc"],
    )

    # 7. Save model artifact
    all_features = FEATURE_COLUMNS + CATEGORICAL_COLUMNS
    artifact = {
        "model": model,
        "version": version,
        "feature_columns": all_features,
        "categorical_columns": cat_cols,
        "metrics": metrics,
        "cutoff_year": cutoff_year,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    model_path = MODELS_DIR / f"{version}.joblib"
    joblib.dump(artifact, model_path)
    logger.info("Model saved to %s", model_path)

    # 8. Register in DB
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        mv = ModelVersion(
            id=uuid.uuid4(),
            version=version,
            description=description
            or f"LightGBM binary classifier (cutoff={cutoff_year})",
            accuracy=metrics["accuracy"],
        )
        session.merge(mv)
        session.commit()
        logger.info("Model version '%s' registered in DB", version)
    engine.dispose()

    return metrics
