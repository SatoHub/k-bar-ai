"""
荒れ度スコア (race-level upset score) — Phase 1 productized.

Predicts how likely a race is to be an upset (本命人気馬が崩れて高配当になる),
from odds dispersion + the main model's own (un)confidence. Validated on
5,563 held-out races: AUC 0.654, monotonic calibration (詳細 docs/20260621-market-edge-design.md).

The trained model is tiny (StandardScaler + LogisticRegression), saved to
``models/upset_score.joblib``. Inference is instant and runs at API read-time,
so no new DB table / migration is needed.
"""

from __future__ import annotations

import datetime
import logging

import joblib
import numpy as np
import pandas as pd

from app.ml.config import MODELS_DIR

logger = logging.getLogger(__name__)

ARTIFACT_PATH = MODELS_DIR / "upset_score.joblib"

UPSET_FEATS = [
    "fav1_odds",
    "fav1_q",
    "gap12_odds",
    "norm_entropy",
    "frac_sub10",
    "field_size",
    "max_p_main",
    "std_p_main",
    "pmain_entropy",
]


def race_features(odds: np.ndarray, fav: np.ndarray, p_main: np.ndarray) -> dict:
    """Compute upset signals for one race from per-horse arrays.

    Args:
        odds:   win odds per horse (>0)
        fav:    popularity rank per horse (1 = most popular)
        p_main: main model's place-probability per horse
    """
    n = len(odds)
    inv = np.where(odds > 0, 1.0 / odds, 0.0)
    q = inv / inv.sum() if inv.sum() > 0 else np.full(n, 1.0 / n)
    norm_entropy = float(-(q * np.log(q + 1e-12)).sum() / np.log(n)) if n > 1 else 0.0

    order = np.argsort(fav)
    fav1_odds = float(odds[order[0]])
    fav2_odds = float(odds[order[1]]) if n >= 2 else fav1_odds
    fav1_q = float(q[order[0]])

    pq = p_main / p_main.sum() if p_main.sum() > 0 else np.full(n, 1.0 / n)
    pmain_entropy = (
        float(-(pq * np.log(pq + 1e-12)).sum() / np.log(n)) if n > 1 else 0.0
    )

    return {
        "fav1_odds": fav1_odds,
        "fav1_q": fav1_q,
        "gap12_odds": fav2_odds - fav1_odds,
        "norm_entropy": norm_entropy,
        "frac_sub10": float((odds < 10).mean()),
        "field_size": float(n),
        "max_p_main": float(p_main.max()),
        "std_p_main": float(p_main.std()),
        "pmain_entropy": pmain_entropy,
    }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
_cache: dict | None = None


def load() -> dict | None:
    """Load (and cache) the trained artifact, or None if not trained yet."""
    global _cache
    if _cache is None:
        if not ARTIFACT_PATH.exists():
            return None
        _cache = joblib.load(ARTIFACT_PATH)
    return _cache


def _level(percentile: float) -> tuple[str, str]:
    """Map distribution percentile to a (level, hint) pair."""
    if percentile >= 0.70:
        return (
            "high",
            "波乱含み。本命の厚張りより、軸+人気薄まで広げたフォーメーション/ボックス推奨。",
        )
    if percentile <= 0.40:
        return "low", "堅め。上位人気で順当に決まりやすい。"
    return "mid", "標準。中位人気まで押さえるのが無難。"


def score_race(
    entries: list[dict] | pd.DataFrame,
) -> dict | None:
    """
    Compute the upset score for one race.

    Args:
        entries: list of dicts (or DataFrame) each with keys/columns
            ``win_odds``, ``win_favorite``, ``predicted_score`` (= main model p_main).

    Returns dict {score, percentile, level, expected_upset_rate, hint} or None
    if the model is untrained or inputs are insufficient (e.g. odds not yet set).
    """
    art = load()
    if art is None:
        return None

    df = pd.DataFrame(entries) if not isinstance(entries, pd.DataFrame) else entries
    need = {"win_odds", "win_favorite", "predicted_score"}
    if not need.issubset(df.columns):
        return None
    df = df.dropna(subset=["win_odds", "win_favorite", "predicted_score"])
    df = df[df["win_odds"] > 0]
    if len(df) < 3 or (df["win_favorite"] == 1).sum() != 1:
        return None

    feat = race_features(
        df["win_odds"].to_numpy(float),
        df["win_favorite"].to_numpy(float),
        df["predicted_score"].to_numpy(float),
    )
    X = pd.DataFrame([[feat[f] for f in UPSET_FEATS]], columns=UPSET_FEATS)
    Xs = art["scaler"].transform(X)
    score = float(art["model"].predict_proba(Xs)[0, 1])

    thr = art["score_quantiles"]  # 99 quantile boundaries (1..99 pct)
    percentile = float(np.searchsorted(thr, score) / 100.0)
    level, hint = _level(percentile)

    return {
        "score": round(score, 4),
        "percentile": round(percentile, 2),
        "level": level,
        "expected_upset_rate": round(score, 3),
        "hint": hint,
    }


# ---------------------------------------------------------------------------
# Training (one-time / on model refresh)
# ---------------------------------------------------------------------------
def train_and_save(main_version: str = "v1.0.0", cutoff_year: int = 2020) -> dict:
    """Fit the upset model on historical races and persist the artifact."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    from app.ml.features import build_feature_matrix

    logger.info("Building feature matrix...")
    df = build_feature_matrix()
    df = df[df["finish_position"].notna()].copy()
    df = df[
        df["win_favorite"].notna() & df["win_odds"].notna() & (df["win_odds"] > 0)
    ].copy()

    main_art = joblib.load(MODELS_DIR / f"{main_version}.joblib")
    df["p_main"] = main_art["model"].predict(df[main_art["feature_columns"]])

    logger.info("Aggregating race-level features...")
    rows = []
    for _, g in df.groupby("race_id_str"):
        if g["win_favorite"].nunique() < 3 or (g["win_favorite"] == 1).sum() != 1:
            continue
        feat = race_features(
            g["win_odds"].to_numpy(float),
            g["win_favorite"].to_numpy(float),
            g["p_main"].to_numpy(float),
        )
        fav1_finish = float(g.loc[g["win_favorite"] == 1, "finish_position"].iloc[0])
        feat["year"] = int(g["race_date"].dt.year.iloc[0])
        feat["upset"] = int(fav1_finish > 3)
        rows.append(feat)
    races = pd.DataFrame(rows).dropna(subset=UPSET_FEATS)

    train = races[races["year"] < cutoff_year]
    test = races[races["year"] >= cutoff_year]

    scaler = StandardScaler().fit(train[UPSET_FEATS])
    clf = LogisticRegression(max_iter=1000).fit(
        scaler.transform(train[UPSET_FEATS]), train["upset"]
    )

    auc = float(
        roc_auc_score(
            test["upset"], clf.predict_proba(scaler.transform(test[UPSET_FEATS]))[:, 1]
        )
    )
    # score distribution (use all races) for percentile mapping
    all_scores = clf.predict_proba(scaler.transform(races[UPSET_FEATS]))[:, 1]
    quantiles = np.quantile(all_scores, np.arange(1, 100) / 100.0)

    artifact = {
        "scaler": scaler,
        "model": clf,
        "features": UPSET_FEATS,
        "score_quantiles": quantiles,
        "test_auc": auc,
        "base_rate": float(races["upset"].mean()),
        "n_races": int(len(races)),
        "main_version": main_version,
        "cutoff_year": cutoff_year,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    joblib.dump(artifact, ARTIFACT_PATH)
    logger.info(
        "Saved upset model to %s (test AUC=%.4f, n=%d)", ARTIFACT_PATH, auc, len(races)
    )
    return {"test_auc": auc, "n_races": len(races), "path": str(ARTIFACT_PATH)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    print(train_and_save())
