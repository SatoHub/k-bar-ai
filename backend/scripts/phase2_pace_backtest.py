"""
Phase 2 (情報エッジ) backtest — does pace / running-style information let the
odds-INDEPENDENT model finally beat naive popularity on ヒモ selection?

Phase 1 showed an odds-free model picks ヒモ *worse* than just boxing 人気1-8.
The hypothesis: that's because it lacks information the market under-weights —
specifically 脚質 (running style) and 展開 (pace scenario). Those are computable
from historical ``corner_pos_4`` (final-corner position), which is ~100% present
for 2012-2021 (the test era), so we can validate the idea NOW without scraping.

We compare three ヒモ selectors on the same upset-flagged test races:
  - naive     : 人気3-8 を機械的に
  - oddsfree  : Phase 1 odds-free model (no pace)
  - +pace     : odds-free model + 脚質/展開 features

Run from backend/:
    uv run python -m scripts.phase2_pace_backtest [--cutoff 2020] [--flag-quantile 0.7] [--himo 6]

NOTE: forward DEPLOYMENT needs the results scraper to capture corner_pos again
(currently 0% for 2026). This script only answers "is it worth that work?".
"""

from __future__ import annotations

import argparse
import logging
import sys

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from app.config import settings
from app.ml.config import (
    CATEGORICAL_COLUMNS,
    LGBM_EARLY_STOPPING_ROUNDS,
    LGBM_NUM_BOOST_ROUND,
    LGBM_PARAMS,
    MODELS_DIR,
    TARGET_COLUMN,
)
from app.ml.features import build_feature_matrix
from app.ml.oddsfree import oddsfree_feature_columns
from app.ml.upset_score import UPSET_FEATS, race_features

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("phase2")

MAIN_VERSION = "v1.0.0"
PACE_FEATS = [
    "horse_style",
    "style_consistency",
    "race_n_front",
    "race_pace_pressure",
    "style_vs_pace",
]


def _load_corner() -> pd.DataFrame:
    """entry_id -> corner_pos_4 from DB."""
    eng = create_engine(settings.database_url_sync)
    df = pd.read_sql(
        "SELECT re.id AS entry_id, re.corner_pos_4 "
        "FROM race_entries re JOIN races r ON r.id = re.race_id "
        "WHERE re.finish_position IS NOT NULL",
        eng,
    )
    eng.dispose()
    return df


def _add_pace_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute leak-free 脚質 (running style) and 展開 (pace) features (vectorized)."""
    field = df.groupby("race_id_str")["entry_id"].transform("size")

    # forwardness in a past race: 1.0 = led at last corner, 0.0 = last.
    cp = pd.to_numeric(df["corner_pos_4"], errors="coerce")
    df["forwardness"] = np.where(
        (field > 1) & cp.notna(),
        1.0 - (cp - 1.0) / (field - 1.0),
        np.nan,
    )

    # horse style = mean forwardness over PRIOR races only (current excluded), NaN-skipping
    df = df.sort_values(["horse_uuid", "race_date", "race_id_str"]).copy()
    df["_f0"] = df["forwardness"].fillna(0.0)
    df["_v"] = df["forwardness"].notna().astype(float)
    df["_f2"] = (df["forwardness"] ** 2).fillna(0.0)
    g = df.groupby("horse_uuid")
    prior_sum = g["_f0"].cumsum() - df["_f0"]
    prior_cnt = g["_v"].cumsum() - df["_v"]
    prior_sq = g["_f2"].cumsum() - df["_f2"]
    with np.errstate(invalid="ignore", divide="ignore"):
        style = prior_sum / prior_cnt
        var = prior_sq / prior_cnt - style**2
    df["horse_style"] = style.where(prior_cnt > 0).fillna(0.5)
    df["style_consistency"] = (
        np.sqrt(var.clip(lower=0)).where(prior_cnt > 1).fillna(0.3)
    )

    # race-level 展開: front-runner count + pace pressure (fast pace favors closers)
    is_front = (df["horse_style"] > 0.65).astype(float)
    df["race_n_front"] = (
        df.assign(_fr=is_front).groupby("race_id_str")["_fr"].transform("sum")
    )
    df["race_pace_pressure"] = df.groupby("race_id_str")["horse_style"].transform(
        lambda s: s.nlargest(min(3, len(s))).mean()
    )
    # interaction: a closer (low style) in a high-pressure race is advantaged
    df["style_vs_pace"] = df["race_pace_pressure"] - df["horse_style"]
    df.drop(columns=["_f0", "_v", "_f2"], inplace=True)
    return df


def _train_lgb(train_df, feats, cat_cols):
    X = train_df[feats]
    y = train_df[TARGET_COLUMN].values.astype(np.float64)
    vc = int(len(X) * 0.9)
    tr = lgb.Dataset(
        X.iloc[:vc], label=y[:vc], categorical_feature=cat_cols, free_raw_data=False
    )
    va = lgb.Dataset(
        X.iloc[vc:],
        label=y[vc:],
        categorical_feature=cat_cols,
        free_raw_data=False,
        reference=tr,
    )
    return lgb.train(
        LGBM_PARAMS,
        tr,
        num_boost_round=LGBM_NUM_BOOST_ROUND,
        valid_sets=[va],
        valid_names=["val"],
        callbacks=[
            lgb.early_stopping(LGBM_EARLY_STOPPING_ROUNDS),
            lgb.log_evaluation(0),
        ],
    )


def _coverage(df, flagged_ids, score_col, K, restrict_band=None):
    """Trifecta-box hit rate + longshot capture for a ヒモ selector."""
    box_hits, longs_hit, longs_tot = [], 0, 0
    for rid in flagged_ids:
        g = df[df["race_id_str"] == rid]
        actual_top3 = set(g.nsmallest(3, "finish_position")["entry_id"])
        axis = set(g.nsmallest(2, "win_favorite")["entry_id"])
        if score_col == "__naive__":
            himo = set(g[g["win_favorite"].between(3, 2 + K)]["entry_id"])
        else:
            pool = g[g["win_favorite"] >= 3]
            if restrict_band is not None:
                pool = pool[pool["win_favorite"] <= restrict_band]
            himo = set(pool.nlargest(K, score_col)["entry_id"])
        sel = axis | himo
        box_hits.append(len(actual_top3 & sel) == 3)
        for _, row in g[
            (g["finish_position"] <= 3) & (g["win_favorite"] >= 6)
        ].iterrows():
            longs_tot += 1
            if row["entry_id"] in himo:
                longs_hit += 1
    return (
        np.mean(box_hits) if box_hits else 0,
        (longs_hit / longs_tot if longs_tot else 0),
        longs_tot,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=int, default=2020)
    ap.add_argument("--flag-quantile", type=float, default=0.70)
    ap.add_argument("--himo", type=int, default=6)
    args = ap.parse_args()

    logger.info("Building feature matrix...")
    df = build_feature_matrix()
    df = df[df["finish_position"].notna()].copy()
    df = df[
        df["win_favorite"].notna() & df["win_odds"].notna() & (df["win_odds"] > 0)
    ].copy()

    logger.info("Merging corner_pos and computing pace features...")
    corner = _load_corner()
    df = df.merge(corner, on="entry_id", how="left")
    df = _add_pace_features(df)

    # main model p_main
    main_art = joblib.load(MODELS_DIR / f"{MAIN_VERSION}.joblib")
    df["p_main"] = main_art["model"].predict(df[main_art["feature_columns"]])

    cat_cols = [c for c in CATEGORICAL_COLUMNS if c in df.columns]
    train_df = df[df["race_date"].dt.year < args.cutoff]

    # model A: odds-free (Phase 1)
    of_feats = oddsfree_feature_columns()
    logger.info("Training odds-free (no pace)...")
    m_of = _train_lgb(train_df, of_feats, cat_cols)
    df["p_indep"] = m_of.predict(df[of_feats])

    # model B: odds-free + pace
    pace_feats = of_feats + PACE_FEATS
    logger.info("Training odds-free + pace...")
    m_pace = _train_lgb(train_df, pace_feats, cat_cols)
    df["p_pace"] = m_pace.predict(df[pace_feats])

    # myoumi vs market place-rate by 人気
    place_rate = train_df.groupby("win_favorite")["is_place"].mean()
    df["market_place"] = df["win_favorite"].map(place_rate).fillna(0.1)
    df["myoumi_of"] = df["p_indep"] - df["market_place"]
    df["myoumi_pace"] = df["p_pace"] - df["market_place"]

    # flag upset races on test set with the productized upset model
    up = joblib.load(MODELS_DIR / "upset_score.joblib")
    test = df[df["race_date"].dt.year >= args.cutoff]
    rows = []
    for rid, g in test.groupby("race_id_str"):
        if g["win_favorite"].nunique() < 3 or (g["win_favorite"] == 1).sum() != 1:
            continue
        feat = race_features(
            g["win_odds"].to_numpy(float),
            g["win_favorite"].to_numpy(float),
            g["p_main"].to_numpy(float),
        )
        rows.append({"race_id_str": rid, **feat})
    rdf = pd.DataFrame(rows).dropna(subset=UPSET_FEATS)
    rdf["upset_score"] = up["model"].predict_proba(
        up["scaler"].transform(rdf[UPSET_FEATS])
    )[:, 1]
    thr = rdf["upset_score"].quantile(args.flag_quantile)
    flagged = set(rdf[rdf["upset_score"] >= thr]["race_id_str"])
    logger.info("Flagged %d upset races", len(flagged))

    K = args.himo
    print("\n" + "=" * 72)
    print("【Phase2】荒れ判定レースでのヒモ選択 比較 (軸=人気1,2 + ヒモ%d頭)" % K)
    print("=" * 72)
    print(f"  対象レース: {len(flagged)}")
    print(f"  {'手法':<26}{'三連複box的中':>14}{'人気薄(>=6)捕捉':>16}")
    print("  " + "-" * 56)
    for label, col, band in [
        ("naive (人気3-8)", "__naive__", None),
        ("oddsfree (脚質なし)", "myoumi_of", None),
        ("oddsfree + 脚質/展開", "myoumi_pace", None),
        ("+脚質/展開 (人気<=10限定)", "myoumi_pace", 10),
    ]:
        box, longs, tot = _coverage(test, flagged, col, K, restrict_band=band)
        print(f"  {label:<26}{box:>13.1%}{longs:>15.1%}")
    print(f"\n  (人気薄好走の母数: {tot}頭)")

    # pace feature importance in model B
    imp = sorted(
        zip(pace_feats, m_pace.feature_importance(importance_type="gain")),
        key=lambda x: -x[1],
    )
    print("\n  --- +pace モデルの脚質/展開特徴量の重要度(gain) ---")
    for name, gain in imp:
        if name in PACE_FEATS:
            print(f"   {name:20s} {gain:>12.0f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
