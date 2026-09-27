"""
「オッズ非依存モデルは市場より良い確率を出せているか」を out-of-sample で検証する。

判定基準は **測定前に** `docs/20260927-oddsfree-edge-criteria.md` で確定させた。
このスクリプトはその基準を機械的に適用するだけで、基準を後から変えない。

やること:
  1. 修正後の特徴量で oddsfree モデルを再学習する
     - `is_win`  : 単勝オッズと突き合わせて期待値を判定するための本命
     - `is_place`: 既存 v1.0.0_oddsfree の AUC 0.733 がリーク由来だったかの切り分け
  2. 2020年以降（学習に使っていない期間）でキャリブレーションを測る
  3. モデル確率 > 市場確率 の馬（＝妙味馬）を抽出して単勝 ROI を測る
  4. ベースライン（全馬均等 / 1番人気）と比べる

出力は標準出力と JSON。**DB への書き込みは行わない。**

実行:
    cd backend && PYTHONPATH=. uv run python scripts/oddsfree_edge_eval.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.config import MODELS_DIR  # noqa: E402
from app.ml.edge_eval import (  # noqa: E402
    ECE_TOLERANCE,
    VERDICT_NO,
    VERDICT_UNDECIDABLE,
    VERDICT_YES,
    calibration,
    market_implied_prob,
    normalize_within_race,
    roi_summary,
)
from app.ml.features import build_feature_matrix  # noqa: E402
from app.ml.oddsfree import (  # noqa: E402
    artifact_path,
    load_oddsfree,
    oddsfree_feature_columns,
    train_oddsfree_model,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("oddsfree_edge_eval")

CUTOFF_YEAR = 2020
#: 主判定の閾値。事前登録済み（docs §2「多重比較の扱い」）。後から変えない。
PRIMARY_EDGE_THRESHOLD = 0.0
#: 探索用。ここで良い数字が出ても「見込みあり」の根拠にはしない。
EXPLORATORY_EDGE_THRESHOLDS = [0.01, 0.02, 0.03, 0.05, 0.10]


def _hr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _fmt_roi(r: dict) -> str:
    if r["bets"] == 0:
        return f"{r['label']:<34} 対象0点"
    lo, hi = r["ci95"]
    return (
        f"{r['label']:<34} {r['bets']:>7,}点 "
        f"的中{r['hit_rate'] * 100:>5.1f}% "
        f"ROI {r['roi'] * 100:>6.1f}% "
        f"CI[{lo * 100:>6.1f}, {hi * 100:>6.1f}] "
        f"必要{r['required_bets_for_target']:>9,.0f}点 "
        f"平均{r['mean_odds']:>6.1f}倍  {r['verdict']}"
    )


def _train_or_load(version: str, target: str, df: pd.DataFrame, retrain: bool) -> dict:
    path = artifact_path(version)
    if path.exists() and not retrain:
        art = load_oddsfree(version)
        if art.get("target_column") == target:
            logger.info("既存の %s を再利用する", path.name)
            return art
        logger.info(
            "%s は target=%s なので再学習する", path.name, art.get("target_column")
        )
    logger.info("学習開始: %s (target=%s)", path.name, target)
    return train_oddsfree_model(
        version=version, cutoff_year=CUTOFF_YEAR, df=df, target_column=target
    )["artifact"]


def _print_calibration(name: str, cal: dict) -> None:
    print(f"\n--- {name} ---")
    if cal["ece"] is None:
        print("  測定不能（対象0件）")
        return
    print(
        f"  ECE = {cal['ece']:.4f}  (許容 {ECE_TOLERANCE})  "
        f"Brier = {cal['brier']:.5f}  n = {cal['n']:,}  "
        f"→ {'OK' if cal['calibration_ok'] else '🔴 崩れている'}"
    )
    print(f"  {'ビン':<4}{'件数':>9}{'予測平均':>10}{'実測勝率':>10}{'ずれ':>9}")
    for b in cal["bins"]:
        print(
            f"  {b['bin']:<4}{b['count']:>9,}{b['mean_predicted'] * 100:>9.2f}%"
            f"{b['actual_rate'] * 100:>9.2f}%{b['gap'] * 100:>+8.2f}pp"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--retrain", action="store_true", help="既存 artifact があっても再学習する"
    )
    ap.add_argument("--out", default="oddsfree_edge_eval.json")
    args = ap.parse_args()

    results: dict = {"criteria_doc": "docs/20260927-oddsfree-edge-criteria.md"}

    _hr("0. 特徴量行列の構築（修正後の features.py）")
    df = build_feature_matrix()
    print(f"全行 {len(df):,} / 期間 {df['race_date'].min()} 〜 {df['race_date'].max()}")

    # ------------------------------------------------ 1. 再学習
    _hr("1. 再学習（修正後の特徴量・日付ベース検証分割）")
    art_win = _train_or_load("v1.2.0_win", "is_win", df, args.retrain)
    art_place = _train_or_load("v1.2.0", "is_place", df, args.retrain)
    for tag, art in [("is_win", art_win), ("is_place", art_place)]:
        m = art["metrics"]
        print(
            f"  target={tag:<9} AUC={m.get('roc_auc'):.5f} "
            f"train={m.get('train_rows'):,} test={m.get('test_rows'):,} "
            f"base_rate={m.get('base_rate'):.4f}"
        )
    results["retrained"] = {
        "is_win": art_win["metrics"],
        "is_place": art_place["metrics"],
    }
    # 既存（バグ修正前に学習した）モデルの記録値。今の特徴量で採点しても
    # 学習時と特徴量の意味が違うため、**数値の比較対象にはしない**。
    try:
        old = load_oddsfree("v1.0.0")
        results["legacy_v1_0_0_oddsfree"] = {
            "recorded_metrics": old["metrics"],
            "created_at": old["created_at"],
            "note": "バグ修正前に学習。記録値であり、今の特徴量での再評価ではない",
        }
        print(
            f"  [参考] 既存 v1.0.0_oddsfree の記録値 AUC="
            f"{old['metrics'].get('roc_auc'):.5f} "
            f"(学習 {old['created_at'][:10]} = バグ修正前 / target=is_place)"
        )
    except FileNotFoundError:
        pass

    # ------------------------------------------------ 2. OOS 集合
    _hr("2. 評価集合（out-of-sample: 2020年以降）")
    feats = oddsfree_feature_columns()
    oos = df[df["race_date"].dt.year >= CUTOFF_YEAR].copy()
    oos = oos[
        oos["finish_position"].notna()
        & oos["win_odds"].notna()
        & (oos["win_odds"].astype(float) > 0)
    ].copy()
    oos = oos.reset_index(drop=True)
    oos["is_win"] = (oos["finish_position"] == 1).astype("float64")
    print(
        f"{len(oos):,} 行 / {oos['race_id_str'].nunique():,} レース / "
        f"{oos['race_date'].min()} 〜 {oos['race_date'].max()}"
    )
    print(f"実測の1着率 = {oos['is_win'].mean():.4f}")

    # 確率をそろえる
    oos["p_model_raw"] = art_win["model"].predict(oos[feats])
    oos["p_model"] = normalize_within_race(oos["p_model_raw"], oos["race_id_str"])
    oos["p_market"] = market_implied_prob(
        oos["win_odds"], oos["race_id_str"], method="normalized"
    )
    oos["p_market_takeout"] = market_implied_prob(
        oos["win_odds"], oos["race_id_str"], method="takeout"
    )
    oos = oos[oos["p_model"].notna() & oos["p_market"].notna()].copy()
    oos["edge"] = oos["p_model"] - oos["p_market"]
    oos["ev"] = oos["p_model"] * oos["win_odds"].astype(float)

    # ------------------------------------------------ 3. キャリブレーション
    _hr("3. キャリブレーション（EV判定の前提。ここが崩れていたら EV 戦略は成立しない）")
    cal = {
        "model_raw": calibration(oos["p_model_raw"], oos["is_win"]),
        "model_normalized": calibration(oos["p_model"], oos["is_win"]),
        "market_normalized": calibration(oos["p_market"], oos["is_win"]),
    }
    _print_calibration("モデル（生の出力）", cal["model_raw"])
    _print_calibration("モデル（レース内正規化）", cal["model_normalized"])
    _print_calibration("市場（オッズ→勝率・比較の基準）", cal["market_normalized"])
    results["calibration"] = cal

    # ------------------------------------------------ 4. ROI
    _hr("4. 単勝 ROI（フラットベット・確定オッズで採点）")
    print(
        "凡例: CI=95% percentile bootstrap / 必要点数=CI半幅0.10にするのに要る点数\n"
        "      損益分岐は ROI 100%。判定は事前登録した基準による。\n"
    )

    def roi(mask: pd.Series | None, label: str) -> dict:
        sub = oos if mask is None else oos[mask]
        return roi_summary(sub["win_odds"], sub["is_win"], label=label)

    print("[ベースライン]")
    base = [
        roi(None, "全馬均等買い"),
        roi(oos["win_favorite"] == 1, "1番人気（人気タイ含む）"),
        roi(
            oos.index.isin(
                oos.loc[oos.groupby("race_id_str")["p_market"].idxmax()].index
            ),
            "市場最上位1頭（オッズ最低）",
        ),
    ]
    for r in base:
        print("  " + _fmt_roi(r))

    print("\n[モデルの素の使い方（市場と比べない）]")
    naive = [
        roi(
            oos.index.isin(
                oos.loc[oos.groupby("race_id_str")["p_model"].idxmax()].index
            ),
            "モデル最上位1頭",
        )
    ]
    for r in naive:
        print("  " + _fmt_roi(r))

    print(f"\n[🔴 主判定（事前登録）: edge > {PRIMARY_EDGE_THRESHOLD}]")
    primary = roi(
        oos["edge"] > PRIMARY_EDGE_THRESHOLD,
        f"妙味馬 edge>{PRIMARY_EDGE_THRESHOLD}",
    )
    print("  " + _fmt_roi(primary))

    print("\n[探索: edge 閾値を変える（選択バイアスが乗るので判定根拠にしない）]")
    explor = [
        roi(oos["edge"] > t, f"edge>{t:.2f}") for t in EXPLORATORY_EDGE_THRESHOLDS
    ]
    for r in explor:
        print("  " + _fmt_roi(r))

    print("\n[探索: 期待値 EV = モデル確率 × オッズ]")
    ev_rows = [roi(oos["ev"] > t, f"EV>{t:.2f}") for t in [1.0, 1.1, 1.2, 1.5]]
    for r in ev_rows:
        print("  " + _fmt_roi(r))

    print("\n[探索: 妙味馬をオッズ帯で切る（人気薄は必要点数が跳ね上がる）]")
    bands = []
    for lo, hi in [(1, 3), (3, 6), (6, 12), (12, 30), (30, 1e9)]:
        m = (
            (oos["edge"] > PRIMARY_EDGE_THRESHOLD)
            & (oos["win_odds"].astype(float) >= lo)
            & (oos["win_odds"].astype(float) < hi)
        )
        label = f"edge>0 かつ {lo}〜{'∞' if hi > 1e8 else int(hi)}倍"
        bands.append(roi(m, label))
    for r in bands:
        print("  " + _fmt_roi(r))

    print("\n[時系列: 主判定を年別に割る（1つの時期に支えられていないか）]")
    yearly = []
    for y in sorted(oos["race_date"].dt.year.unique()):
        m = (oos["edge"] > PRIMARY_EDGE_THRESHOLD) & (oos["race_date"].dt.year == y)
        yearly.append(roi(m, f"{y}年 edge>0"))
    for r in yearly:
        print("  " + _fmt_roi(r))

    results["roi"] = {
        "baselines": base,
        "model_naive": naive,
        "primary": primary,
        "exploratory_edge": explor,
        "exploratory_ev": ev_rows,
        "odds_bands": bands,
        "yearly": yearly,
    }

    # ------------------------------------------------ 5. 判定
    _hr("5. 事前登録した基準による判定")
    cal_ok = cal["model_normalized"]["calibration_ok"]
    print(
        f"キャリブレーション: ECE={cal['model_normalized']['ece']:.4f} "
        f"(許容 {ECE_TOLERANCE}) → {'OK' if cal_ok else '🔴 崩れている'}"
    )
    print(f"主判定 ROI: {primary['roi'] * 100:.1f}%  {primary['bets']:,}点")
    print(
        f"  CI95 = [{primary['ci95'][0] * 100:.1f}%, {primary['ci95'][1] * 100:.1f}%]"
    )
    print(f"  判定 = {primary['verdict']}（{primary['verdict_reason']}）")

    if not cal_ok:
        final = VERDICT_NO
        reason = (
            "キャリブレーションが許容を超えて崩れているため、"
            "EV（期待値）ベースの戦略は現状成立しない。"
            "ROI の数値は参考値にとどまる"
        )
    elif primary["verdict"] == VERDICT_YES:
        final, reason = VERDICT_YES, primary["verdict_reason"]
    elif primary["verdict"] == VERDICT_NO:
        final, reason = VERDICT_NO, primary["verdict_reason"]
    else:
        final, reason = VERDICT_UNDECIDABLE, primary["verdict_reason"]

    print(f"\n🔴 最終判定: {final}\n   理由: {reason}")
    results["final_verdict"] = {
        "verdict": final,
        "reason": reason,
        "calibration_ok": bool(cal_ok),
    }

    out = Path(args.out)
    out.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nJSON: {out.resolve()}")
    print(f"models: {MODELS_DIR}")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
