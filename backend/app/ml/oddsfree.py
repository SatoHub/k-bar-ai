"""
Odds-independent place-probability model (Phase 1: market-edge).

This trains a LightGBM model that is identical to the main model EXCEPT it
excludes ``win_odds`` and ``win_favorite``. Because it never sees the market's
opinion, its output can *disagree* with the market — which is exactly what we
need to surface under-priced horses (ヒモ妙味) for wide exotic bets in
upset-prone races.

Artifact is saved as ``{version}_oddsfree.joblib`` alongside the main model.
"""

from __future__ import annotations

import datetime
import logging

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

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

logger = logging.getLogger(__name__)

# Features the market has already priced in — excluded on purpose.
ODDS_FEATURES = ["win_odds", "win_favorite"]


def oddsfree_feature_columns() -> list[str]:
    """Numeric features minus odds/popularity, plus all categoricals."""
    numeric = [f for f in FEATURE_COLUMNS if f not in ODDS_FEATURES]
    return numeric + CATEGORICAL_COLUMNS


def artifact_path(version: str = "v1.0.0"):
    return MODELS_DIR / f"{version}_oddsfree.joblib"


def load_oddsfree(version: str = "v1.0.0") -> dict:
    """Load a saved odds-independent model artifact."""
    return joblib.load(artifact_path(version))


def train_oddsfree_model(
    version: str,
    cutoff_year: int = DEFAULT_CUTOFF_YEAR,
    df: pd.DataFrame | None = None,
    target_column: str = TARGET_COLUMN,
) -> dict:
    """
    Train the odds-independent model and save the artifact.

    ⚠️ ``version`` は**必須**。既定値 ``"v1.0.0"`` を残していたため、
       `train_oddsfree_model(target_column="is_win")` のような呼び方で
       **本番名の `v1.0.0_oddsfree.joblib` を別の目的変数で上書き**できた
       （security-reviewer L-7）。呼び出し側に必ず名前を書かせる。

    Args:
        df: optional pre-built feature matrix (build_feature_matrix is
            expensive, so the backtest reuses one already in memory).
        target_column: ``"is_place"``（既定, 3着内）or ``"is_win"``（1着）。
            **単勝オッズと突き合わせて期待値を判定するなら ``"is_win"`` が必要。**
            複勝の払戻オッズは DB に無いため、``is_place`` の確率は
            金銭的な期待値計算には使えない（順位付けにしか使えない）。

    Returns a dict with the trained artifact and test metrics.
    """
    if df is None:
        logger.info("Building feature matrix...")
        df = build_feature_matrix()

    if target_column not in df.columns:
        raise KeyError(
            f"target_column '{target_column}' が特徴量行列に無い "
            f"(利用可能: is_win / is_place)"
        )

    feats = oddsfree_feature_columns()
    cat_cols = [c for c in CATEGORICAL_COLUMNS if c in df.columns]

    train = df[df["race_date"].dt.year < cutoff_year]
    test = df[df["race_date"].dt.year >= cutoff_year]
    logger.info(
        "oddsfree train=%d test=%d (cutoff=%d, target=%s)",
        len(train),
        len(test),
        cutoff_year,
        target_column,
    )

    X_train = train[feats].copy()
    y_train = train[target_column].values.astype(np.float64)
    X_test = test[feats].copy()
    y_test = test[target_column].values.astype(np.float64)

    # 検証分割は**日付**で切る。
    # ⚠️ 以前は `iloc[:90%]` の位置ベースだった。build_feature_matrix が
    #    返す並び順に依存するため、コメントの意図（時系列の後ろ10%）とは
    #    異なる集合になりうる。trainer.py で同じ欠陥を修正済み（2026-09-27）。
    val_start = train["race_date"].quantile(0.9)
    val_mask = (train["race_date"] >= val_start).to_numpy()
    X_tr, y_tr = X_train[~val_mask], y_train[~val_mask]
    X_val, y_val = X_train[val_mask], y_train[val_mask]
    logger.info(
        "oddsfree validation split: >= %s (train=%d, val=%d)",
        pd.Timestamp(val_start).date(),
        len(y_tr),
        len(y_val),
    )

    train_set = lgb.Dataset(
        X_tr, label=y_tr, categorical_feature=cat_cols, free_raw_data=False
    )
    val_set = lgb.Dataset(
        X_val,
        label=y_val,
        categorical_feature=cat_cols,
        free_raw_data=False,
        reference=train_set,
    )

    logger.info("Training odds-independent LightGBM...")
    model = lgb.train(
        LGBM_PARAMS,
        train_set,
        num_boost_round=LGBM_NUM_BOOST_ROUND,
        valid_sets=[train_set, val_set],
        valid_names=["train", "val"],
        callbacks=[
            lgb.early_stopping(LGBM_EARLY_STOPPING_ROUNDS),
            lgb.log_evaluation(200),
        ],
    )

    metrics = {"target_column": target_column, "train_rows": int(len(y_train))}
    if len(y_test) > 0:
        y_prob = model.predict(X_test)
        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob))
        metrics["test_rows"] = int(len(y_test))
        metrics["base_rate"] = float(np.mean(y_test))
        logger.info(
            "oddsfree test ROC-AUC=%.4f (target=%s, base_rate=%.4f)",
            metrics["roc_auc"],
            target_column,
            metrics["base_rate"],
        )

    artifact = {
        "model": model,
        "version": f"{version}_oddsfree",
        "feature_columns": feats,
        "categorical_columns": cat_cols,
        "target_column": target_column,
        "metrics": metrics,
        "cutoff_year": cutoff_year,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    path = artifact_path(version)
    joblib.dump(artifact, path)
    logger.info("Saved odds-independent model to %s", path)

    return {"artifact": artifact, "metrics": metrics, "path": str(path)}
