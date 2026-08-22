"""
Phase 1 market-edge backtest.

Validates two ideas on held-out (>= cutoff year) races, using ONLY data already
in the DB — no new scraping required:

  1. 荒れ度スコア (race-level upset score)
     Can we predict *which races will be upsets* from odds dispersion + the main
     model's own (un)confidence? A logistic model is fit on train-year races and
     evaluated on test-year races. We report AUC and a calibration table.

  2. ヒモ妙味スコア (odds-independent under-pricing)
     In upset-flagged races, does selecting ヒモ (2nd/3rd-place candidates) by an
     odds-INDEPENDENT model capture the actual longshot placers better than naive
     popularity-based selection? Coverage is compared head-to-head.

Run from backend/:
    uv run python -m scripts.phase1_edge_backtest [--cutoff 2020] [--flag-quantile 0.7] [--himo 6]

NOTE: ROI in yen needs trifecta payout data (limited historically); this script
measures *hit/coverage*, which is what tells us whether we can "narrow the field".
"""

from __future__ import annotations

import argparse
import logging
import sys

import joblib
import numpy as np
import pandas as pd

from app.ml.config import MODELS_DIR
from app.ml.features import build_feature_matrix
from app.ml.oddsfree import (
    artifact_path,
    load_oddsfree,
    oddsfree_feature_columns,
    train_oddsfree_model,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("phase1")

MAIN_VERSION = "v1.0.0"


# ---------------------------------------------------------------------------
# Race-level upset features
# ---------------------------------------------------------------------------
def _race_features(g: pd.DataFrame) -> dict:
    """Compute upset signals for a single race group."""
    odds = g["win_odds"].astype(float).to_numpy()
    fav = g["win_favorite"].astype(float).to_numpy()
    n = len(g)

    inv = np.where(odds > 0, 1.0 / odds, 0.0)
    q = inv / inv.sum() if inv.sum() > 0 else np.full(n, 1.0 / n)
    norm_entropy = float(-(q * np.log(q + 1e-12)).sum() / np.log(n)) if n > 1 else 0.0

    order = np.argsort(fav)  # by popularity (1 = most popular)
    fav1_odds = float(odds[order[0]]) if n >= 1 else np.nan
    fav2_odds = float(odds[order[1]]) if n >= 2 else np.nan
    fav1_q = float(q[order[0]]) if n >= 1 else np.nan

    pmain = g["p_main"].astype(float).to_numpy()
    pq = pmain / pmain.sum() if pmain.sum() > 0 else np.full(n, 1.0 / n)
    pmain_entropy = (
        float(-(pq * np.log(pq + 1e-12)).sum() / np.log(n)) if n > 1 else 0.0
    )

    return {
        "field_size": n,
        "fav1_odds": fav1_odds,
        "fav1_q": fav1_q,
        "gap12_odds": fav2_odds - fav1_odds,
        "norm_entropy": norm_entropy,
        "frac_sub10": float((odds < 10).mean()),
        "max_p_main": float(pmain.max()),
        "mean_p_main": float(pmain.mean()),
        "std_p_main": float(pmain.std()),
        "pmain_entropy": pmain_entropy,
    }


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=int, default=2020)
    ap.add_argument(
        "--flag-quantile",
        type=float,
        default=0.70,
        help="races with upset_score above this quantile are flagged 荒れ",
    )
    ap.add_argument(
        "--himo", type=int, default=6, help="number of ヒモ candidates per side"
    )
    ap.add_argument("--retrain-oddsfree", action="store_true")
    args = ap.parse_args()

    # ---------------------------------------------------------------- load data
    logger.info("Building feature matrix (this loads the full history)...")
    df = build_feature_matrix()
    df = df[df["finish_position"].notna()].copy()
    df = df[
        df["win_favorite"].notna() & df["win_odds"].notna() & (df["win_odds"] > 0)
    ].copy()

    # ---------------------------------------------------- main model p_main
    main_art = joblib.load(MODELS_DIR / f"{MAIN_VERSION}.joblib")
    main_feats = main_art["feature_columns"]
    df["p_main"] = main_art["model"].predict(df[main_feats])
    logger.info("Main model scored %d rows", len(df))

    # ---------------------------------------------- odds-independent p_indep
    if args.retrain_oddsfree or not artifact_path(MAIN_VERSION).exists():
        logger.info("Training odds-independent model...")
        train_oddsfree_model(version=MAIN_VERSION, cutoff_year=args.cutoff, df=df)
    of_art = load_oddsfree(MAIN_VERSION)
    df["p_indep"] = of_art["model"].predict(df[oddsfree_feature_columns()])
    logger.info(
        "Odds-independent model scored %d rows (test AUC=%s)",
        len(df),
        of_art.get("metrics", {}).get("roc_auc"),
    )

    # ---------------------------------------------------- empirical place rate
    train_mask = df["race_date"].dt.year < args.cutoff
    place_rate_by_fav = df[train_mask].groupby("win_favorite")["is_place"].mean()
    # myoumi: model (odds-free) thinks more likely top3 than popularity implies
    df["market_place"] = df["win_favorite"].map(place_rate_by_fav).fillna(0.1)
    df["myoumi"] = df["p_indep"] - df["market_place"]

    # ---------------------------------------------------- race-level table
    logger.info("Aggregating race-level features...")
    rows = []
    for rid, g in df.groupby("race_id_str"):
        if g["win_favorite"].nunique() < 3 or (g["win_favorite"] == 1).sum() != 1:
            continue
        feat = _race_features(g)
        fav1_finish = float(g.loc[g["win_favorite"] == 1, "finish_position"].iloc[0])
        top3 = g.nsmallest(3, "finish_position")
        feat.update(
            race_id_str=rid,
            year=g["race_date"].dt.year.iloc[0],
            fav1_finish=fav1_finish,
            upset=int(fav1_finish > 3),
            top3_fav_sum=float(top3["win_favorite"].sum()),
            top3_max_fav=float(top3["win_favorite"].max()),
        )
        rows.append(feat)
    races = pd.DataFrame(rows).dropna(subset=UPSET_FEATS)
    logger.info("Races usable: %d", len(races))

    rtrain = races[races["year"] < args.cutoff]
    rtest = races[races["year"] >= args.cutoff]

    # ---------------------------------------------------- fit 荒れ度スコア
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(rtrain[UPSET_FEATS])
    clf = LogisticRegression(max_iter=1000).fit(
        scaler.transform(rtrain[UPSET_FEATS]), rtrain["upset"]
    )
    rtest = rtest.copy()
    rtest["upset_score"] = clf.predict_proba(scaler.transform(rtest[UPSET_FEATS]))[:, 1]

    base_rate = rtest["upset"].mean()
    auc = roc_auc_score(rtest["upset"], rtest["upset_score"])

    print("\n" + "=" * 70)
    print("【1】荒れ度スコア (1人気が複勝圏外=荒れ, test年>=%d)" % args.cutoff)
    print("=" * 70)
    print(f"  test races        : {len(rtest)}")
    print(f"  base upset rate   : {base_rate:.1%}  (1人気が4着以下の割合)")
    print(f"  upset_score AUC   : {auc:.4f}")
    print("\n  --- 荒れ度スコア decile別 実際の荒れ率 (校正) ---")
    rtest["decile"] = pd.qcut(rtest["upset_score"], 10, labels=False, duplicates="drop")
    cal = rtest.groupby("decile").agg(
        n=("upset", "size"),
        actual_upset=("upset", "mean"),
        mean_score=("upset_score", "mean"),
        top3_max_fav=("top3_max_fav", "mean"),
    )
    for d, r in cal.iterrows():
        bar = "#" * int(r["actual_upset"] * 40)
        print(
            f"   D{int(d) + 1:2d} n={int(r['n']):4d} pred={r['mean_score']:.2f} "
            f"actual={r['actual_upset']:.1%} 平均最低人気(top3)={r['top3_max_fav']:.1f} {bar}"
        )

    print("\n  --- ロジスティック係数 (絶対値順, +で荒れ方向) ---")
    coefs = sorted(zip(UPSET_FEATS, clf.coef_[0]), key=lambda x: -abs(x[1]))
    for name, c in coefs:
        print(f"   {name:16s} {c:+.3f}")

    # ---------------------------------------------------- ヒモ妙味 coverage
    flag_thr = rtest["upset_score"].quantile(args.flag_quantile)
    flagged_ids = set(rtest[rtest["upset_score"] >= flag_thr]["race_id_str"])
    K = args.himo

    stats = {"ours": [], "naive": []}
    longshot_capture = {"ours": [0, 0], "naive": [0, 0]}  # [hit, total]
    for rid in flagged_ids:
        g = df[df["race_id_str"] == rid]
        actual_top3 = set(g.nsmallest(3, "finish_position")["horse_uuid"])
        # axis = top2 by main model
        axis = list(g.nsmallest(2, "win_favorite")["horse_uuid"])  # 人気1,2 = 軸 (both)
        # ours: himo by myoumi among 人気>=3
        pool = g[g["win_favorite"] >= 3]
        ours_himo = set(pool.nlargest(K, "myoumi")["horse_uuid"])
        ours_set = set(axis) | ours_himo
        # naive: himo = 人気 3..(2+K)
        naive_himo = set(g[g["win_favorite"].between(3, 2 + K)]["horse_uuid"])
        naive_set = set(axis) | naive_himo

        stats["ours"].append(len(actual_top3 & ours_set) == 3)
        stats["naive"].append(len(actual_top3 & naive_set) == 3)

        # longshot capture: actual top3 horses with 人気>=6
        longs = set(
            g[(g["finish_position"] <= 3) & (g["win_favorite"] >= 6)]["horse_uuid"]
        )
        for h in longs:
            longshot_capture["ours"][1] += 1
            longshot_capture["naive"][1] += 1
            if h in ours_himo:
                longshot_capture["ours"][0] += 1
            if h in naive_himo:
                longshot_capture["naive"][0] += 1

    print("\n" + "=" * 70)
    print(
        "【2】ヒモ妙味カバレッジ (荒れ判定レース=上位%.0f%%, ヒモ各%d頭)"
        % ((1 - args.flag_quantile) * 100, K)
    )
    print("=" * 70)
    print(f"  対象レース: {len(flagged_ids)}  (軸=人気1,2 + ヒモ{K}頭, 計~{2 + K}頭)")
    for name, label in [("ours", "妙味(oddsfree)"), ("naive", "人気順naive")]:
        arr = stats[name]
        hit = np.mean(arr) if arr else 0
        print(
            f"  三連複ボックス的中率 [{label:16s}]: {hit:.1%} ({sum(arr)}/{len(arr)})"
        )
    print("  --- 人気薄(6人気以下)で実際に3着内に来た馬の捕捉率 ---")
    for name, label in [("ours", "妙味(oddsfree)"), ("naive", "人気順naive")]:
        hit, tot = longshot_capture[name]
        rate = hit / tot if tot else 0
        print(f"   [{label:16s}]: {rate:.1%} ({hit}/{tot})")

    print("\n注: ROI(円)は三連複払戻データが歴史的に不足のため未算出。")
    print("    本検証は『荒れを当てられるか』『穴を絞れるか』のカバレッジ評価。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
