"""
「オッズ非依存モデルは市場より良い確率を出せているか」を out-of-sample で検証する。

判定基準は **測定前に** `docs/20260927-oddsfree-edge-criteria.md` で確定させた。
このスクリプトはその基準を機械的に適用するだけで、基準を後から変えない。

やること:
  1. 修正後の特徴量で oddsfree モデルを学習（または検証済みの artifact を再利用）
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
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Windows のコンソール既定は cp932 で、絵文字や一部記号が UnicodeEncodeError に
# なる。**評価の最後（判定の出力）で落ちた**ので必須。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

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
#: 探索行に表示するラベル。主判定と同じ「見込みあり」を出さないための固定文字列。
EXPLORATORY_LABEL = "探索(判定根拠外)"


def _hr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _fmt_roi(r: dict, *, show_verdict: bool = True) -> str:
    """
    1行の要約。

    ⚠️ `show_verdict=False` を既定にしたい誘惑があるが、主判定は必ず出す。
       探索行にだけ verdict を隠す理由は多重比較（§2）で、
       閾値を20本試せばどれか1本が名目5%で「見込みあり」を出すため
       （security-reviewer の実測: 境界で1行あたり 2.7%、20本なら3〜4割）。
    """
    if r["bets"] == 0:
        return f"{r['label']:<34} 対象0点"
    lo, hi = r["ci95"]
    tail = r["verdict"] if show_verdict else EXPLORATORY_LABEL
    return (
        f"{r['label']:<34} {r['bets']:>7,}点 "
        f"的中{r['hit_rate'] * 100:>5.1f}% "
        f"ROI {r['roi'] * 100:>6.1f}% "
        f"CI[{lo * 100:>6.1f}, {hi * 100:>6.1f}] "
        f"必要{r['required_bets_for_target']:>9,.0f}点 "
        f"平均{r['mean_odds']:>6.1f}倍  {tail}"
    )


def _load_validated(version: str, target: str) -> dict | None:
    """
    保存済み artifact を**検証してから**返す。合わなければ None。

    🔴 当初は `target_column` の一致だけを見ていた（code-reviewer H2 /
       security-reviewer H-1）。`cutoff_year` を見ないと、別の cutoff で
       学習した同名 artifact を拾って **学習済み期間を out-of-sample と称して
       ROI を測る**（`phase1_edge_backtest.py` は任意の `--cutoff` で同じ
       パスに書く）。`feature_columns` を見ないと、列の増減や並べ替え後に
       **LightGBM が列名を検証しないまま別物の予測を返す**
       （実測: 列順を入れ替えると予測値が最大 0.869 変わる）。
    """
    path = artifact_path(version)
    if not path.exists():
        return None
    art = load_oddsfree(version)
    checks = {
        "target_column": (art.get("target_column"), target),
        "cutoff_year": (art.get("cutoff_year"), CUTOFF_YEAR),
        "feature_columns": (art.get("feature_columns"), oddsfree_feature_columns()),
    }
    for key, (got, want) in checks.items():
        if got != want:
            got_s = f"{len(got)}列" if key == "feature_columns" else got
            print(f"  {path.name}: {key} が不一致（{got_s}）→ 再学習する")
            return None
    print(
        f"  {path.name}: 検証OK（target={target} / cutoff={CUTOFF_YEAR} / "
        f"{len(art['feature_columns'])}特徴量 / 学習 {art['created_at'][:19]}）"
        f" → **再利用**"
    )
    return art


def _train_or_load(
    version: str, target: str, df: pd.DataFrame | None, retrain: bool
) -> tuple[dict, bool]:
    """(artifact, 再利用したか) を返す。"""
    if not retrain:
        art = _load_validated(version, target)
        if art is not None:
            return art, True
    logger.info("学習開始: %s (target=%s)", artifact_path(version).name, target)
    if df is None:
        logger.info("学習用の特徴量行列を構築する（完走馬のみ）")
        df = build_feature_matrix()
    art = train_oddsfree_model(
        version=version, cutoff_year=CUTOFF_YEAR, df=df, target_column=target
    )["artifact"]
    return art, False


def _print_calibration(name: str, cal: dict) -> None:
    print(f"\n--- {name} ---")
    if cal["ece"] is None:
        print(f"  測定不能（{cal['degenerate_reason']}）")
        return
    status = "OK" if cal["calibration_ok"] else "🔴 使えない"
    print(
        f"  ECE = {cal['ece']:.4f}  (許容 {ECE_TOLERANCE})  "
        f"Brier = {cal['brier']:.5f}  n = {cal['n']:,}  "
        f"有効ビン {cal['n_bins_effective']}/{cal['n_bins_requested']}  → {status}"
    )
    if cal["degenerate"]:
        print(f"  🔴 {cal['degenerate_reason']}")
    print(f"  {'ビン':<4}{'件数':>9}{'予測平均':>10}{'実測勝率':>10}{'ずれ':>9}")
    for b in cal["bins"]:
        print(
            f"  {b['bin']:<4}{b['count']:>9,}{b['mean_predicted'] * 100:>9.2f}%"
            f"{b['actual_rate'] * 100:>9.2f}%{b['gap'] * 100:>+8.2f}pp"
        )


def _json_safe(obj):
    """NaN/inf を null にする。`allow_nan=True` の `NaN` は厳格パーサで落ちる。"""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    return obj


def _measure_feature_skew(oos: pd.DataFrame, booster, feats: list[str]) -> dict:
    """
    評価行列を `include_upcoming=True` で作ったことによる特徴量のずれを測る。

    モデルは `include_upcoming=False` の行列で学習している。評価側に非完走馬・
    未施行レースの行が加わると、`_grouped_window` の窓に入る「直前の行」の
    集合が変わるため、**同じ行の特徴量が学習時と違う値になりうる**
    （code-reviewer M5）。コメントで「小さいはず」と主張せず実測する。
    """
    logger.info("skew 測定用に完走馬のみの行列を構築する")
    finished = build_feature_matrix()
    finished = finished[finished["race_date"].dt.year >= CUTOFF_YEAR]
    missing = [c for c in feats if c not in finished.columns]
    if missing:
        return {"error": f"特徴量不足: {missing}"}
    finished = finished.set_index("entry_id")
    finished = finished[~finished.index.duplicated()]
    common = oos.set_index("entry_id").index.intersection(finished.index)
    if len(common) == 0:
        return {"error": "共通行なし"}
    a = pd.Series(
        booster.predict(oos.set_index("entry_id").loc[common, feats]), index=common
    )
    b = pd.Series(booster.predict(finished.loc[common, feats]), index=common)
    diff = (a - b).abs()
    return {
        "common_rows": int(len(common)),
        "mean_abs_diff": float(diff.mean()),
        "p99_abs_diff": float(diff.quantile(0.99)),
        "max_abs_diff": float(diff.max()),
        "rows_differing_over_0.01": int((diff > 0.01).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--retrain", action="store_true", help="検証済み artifact があっても再学習する"
    )
    ap.add_argument(
        "--measure-skew",
        action="store_true",
        help="include_upcoming の有無で予測がどれだけ動くかを実測する（行列を追加で1本作る）",
    )
    ap.add_argument("--out", default="oddsfree_edge_eval.json")
    args = ap.parse_args()

    results: dict = {"criteria_doc": "docs/20260927-oddsfree-edge-criteria.md"}

    # ------------------------------------------------ 1. 学習 or 検証済み再利用
    _hr("1. oddsfree モデル（修正後の特徴量・日付ベース検証分割）")
    train_df = build_feature_matrix() if args.retrain else None
    art_win, reused_win = _train_or_load("v1.2.0_win", "is_win", train_df, args.retrain)
    art_place, reused_place = _train_or_load(
        "v1.2.0", "is_place", train_df, args.retrain
    )
    del train_df
    for tag, art, reused in [
        ("is_win", art_win, reused_win),
        ("is_place", art_place, reused_place),
    ]:
        m = art["metrics"]
        print(
            f"  target={tag:<9} AUC={m.get('roc_auc'):.5f} "
            f"train={m.get('train_rows'):,} test={m.get('test_rows'):,} "
            f"base_rate={m.get('base_rate'):.4f} "
            f"[{'再利用' if reused else '今回学習'}]"
        )
    results["models"] = {
        "is_win": {
            **art_win["metrics"],
            "reused": reused_win,
            "created_at": art_win["created_at"],
            "cutoff_year": art_win["cutoff_year"],
        },
        "is_place": {
            **art_place["metrics"],
            "reused": reused_place,
            "created_at": art_place["created_at"],
            "cutoff_year": art_place["cutoff_year"],
        },
    }
    # 既存（バグ修正前に学習した）モデルの記録値。今の特徴量で採点しても
    # 学習時と特徴量の意味が違うため、**数値の比較対象にはしない**。
    try:
        old = load_oddsfree("v1.0.0")
    except FileNotFoundError:
        print("  [参考] 既存 v1.0.0_oddsfree が見つからない（比較なし）")
    else:
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

    # ------------------------------------------------ 2. OOS 集合
    _hr("2. 評価集合（out-of-sample: 2020年以降）")
    # 🔴 特徴量の列は **artifact に保存されたもの**を使う。現在の
    #    `oddsfree_feature_columns()` を使うと、列の増減・並べ替えの後に
    #    LightGBM が無警告で別物の予測を返す（code-reviewer H1）。
    feats = art_win["feature_columns"]

    # 🔴 **非完走馬（競走中止など）を落とさない。** codex レビューの指摘。
    #    `build_feature_matrix()` の既定は `finish_position IS NOT NULL` で、
    #    競走中止の馬が消える。これを落とすと2つのバイアスが入る:
    #      (a) 賭けていたはずのハズレが ROI の分母から消えて**楽観側に歪む**
    #      (b) レース内正規化の母数が減り、残った馬の市場確率が過大になる
    #        → エッジが過小になり、選択そのものが歪む
    #    出走取消・競走除外（= 返還される）は `win_odds` が無いので自然に外れる。
    full = build_feature_matrix(include_upcoming=True)
    oos = full[full["race_date"].dt.year >= CUTOFF_YEAR].copy()
    del full

    # まだ結果が無いレース（未施行）は対象外。1頭でも着順が確定していれば施行済み。
    raced = oos.groupby("race_id_str")["finish_position"].transform("count") > 0
    n_unraced = int((~raced).sum())
    oos = oos[raced].copy()

    n_no_odds = int(
        (oos["win_odds"].isna() | (oos["win_odds"].astype(float) <= 0)).sum()
    )
    oos = oos[oos["win_odds"].notna() & (oos["win_odds"].astype(float) > 0)].copy()
    oos = oos.reset_index(drop=True)
    n_nonfinisher = int(oos["finish_position"].isna().sum())
    oos["is_win"] = (oos["finish_position"] == 1).fillna(False).astype("float64")

    # 確率をそろえる
    oos["p_model_raw"] = art_win["model"].predict(oos[feats])
    oos["p_model"] = normalize_within_race(oos["p_model_raw"], oos["race_id_str"])
    oos["p_market"] = market_implied_prob(
        oos["win_odds"], oos["race_id_str"], method="normalized"
    )
    oos["p_market_takeout"] = market_implied_prob(
        oos["win_odds"], oos["race_id_str"], method="takeout"
    )
    # ⚠️ ここで落ちた行数を必ず記録する。黙って母集団が縮むと
    #    「なぜ点数が少ないのか」の診断が消える（security-reviewer M-3）。
    n_before_prob = len(oos)
    oos = oos[oos["p_model"].notna() & oos["p_market"].notna()].copy()
    n_prob_nan = n_before_prob - len(oos)
    oos["edge"] = oos["p_model"] - oos["p_market"]
    oos["edge_takeout"] = oos["p_model"] - oos["p_market_takeout"]
    oos["ev"] = oos["p_model"] * oos["win_odds"].astype(float)

    print(
        f"{len(oos):,} 行 / {oos['race_id_str'].nunique():,} レース / "
        f"{oos['race_date'].min().date()} 〜 {oos['race_date'].max().date()}"
    )
    print(
        f"  未施行レースの行を除外: {n_unraced:,}\n"
        f"  オッズ無し(取消/除外=返還)を除外: {n_no_odds:,}\n"
        f"  非完走(中止等・ハズレとして計上): {n_nonfinisher:,}\n"
        f"  確率が NaN で除外: {n_prob_nan:,}"
    )
    print(f"実測の1着率 = {oos['is_win'].mean():.4f}")
    results["population"] = {
        "rows": int(len(oos)),
        "races": int(oos["race_id_str"].nunique()),
        "non_finishers_counted_as_loss": n_nonfinisher,
        "unraced_rows_excluded": n_unraced,
        "no_odds_rows_excluded": n_no_odds,
        "nan_prob_rows_excluded": n_prob_nan,
        "actual_win_rate": float(oos["is_win"].mean()),
    }

    if args.measure_skew:
        skew = _measure_feature_skew(oos, art_win["model"], feats)
        print(f"  特徴量スキュー実測: {skew}")
        results["feature_skew_vs_training_matrix"] = skew

    # ------------------------------------------------ 3. キャリブレーション
    _hr("3. キャリブレーション（EV判定の前提。崩れていたら EV 戦略は成立しない）")
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
        f"      探索行は多重比較で偽陽性が出るため verdict を出さず"
        f"「{EXPLORATORY_LABEL}」と表示する。\n"
    )

    def roi(mask: pd.Series | np.ndarray | None, label: str) -> dict:
        sub = oos if mask is None else oos[mask]
        return roi_summary(sub["win_odds"], sub["is_win"], label=label)

    print("[ベースライン]")
    base = [
        roi(None, "全馬均等買い"),
        roi(oos["win_favorite"] == 1, "1番人気（人気タイ含む）"),
        roi(
            oos.index.isin(oos.groupby("race_id_str")["p_market"].idxmax()),
            "市場最上位1頭（オッズ最低）",
        ),
    ]
    for r in base:
        print("  " + _fmt_roi(r))

    print("\n[モデルの素の使い方（市場と比べない）]")
    naive = [
        roi(
            oos.index.isin(oos.groupby("race_id_str")["p_model"].idxmax()),
            "モデル最上位1頭",
        )
    ]
    for r in naive:
        print("  " + _fmt_roi(r))

    print(f"\n[🔴 主判定（事前登録）: edge > {PRIMARY_EDGE_THRESHOLD}]")
    primary = roi(
        oos["edge"] > PRIMARY_EDGE_THRESHOLD, f"妙味馬 edge>{PRIMARY_EDGE_THRESHOLD}"
    )
    print("  " + _fmt_roi(primary))

    # 非完走馬を落とした場合との差 = codex が指摘したバイアスの実測値。
    # 「小さいから無視してよい」ではなく**測って示す**。
    bias_check = roi(
        (oos["edge"] > PRIMARY_EDGE_THRESHOLD) & oos["finish_position"].notna(),
        "（参考）完走馬のみに限った場合",
    )
    print("  " + _fmt_roi(bias_check, show_verdict=False))
    if primary["bets"] and bias_check["bets"]:
        print(
            f"  → 非完走馬を落とすと ROI が "
            f"{(bias_check['roi'] - primary['roi']) * 100:+.2f}pp 動く"
            f"（正なら楽観方向に歪む）"
        )
    results["nonfinisher_bias_check"] = bias_check

    # 市場確率の復元方法を takeout 近似に替えた場合（事前登録 §4 で両方出すと決めた）
    takeout_sens = roi(
        oos["edge_takeout"] > PRIMARY_EDGE_THRESHOLD,
        "（参考）市場確率を takeout 近似で",
    )
    print("  " + _fmt_roi(takeout_sens, show_verdict=False))
    results["takeout_method_sensitivity"] = takeout_sens

    print("\n[探索: edge 閾値を変える（選択バイアスが乗るので判定根拠にしない）]")
    explor = [
        roi(oos["edge"] > t, f"edge>{t:.2f}") for t in EXPLORATORY_EDGE_THRESHOLDS
    ]
    for r in explor:
        print("  " + _fmt_roi(r, show_verdict=False))

    print("\n[探索: 期待値 EV = モデル確率 × オッズ]")
    ev_rows = [roi(oos["ev"] > t, f"EV>{t:.2f}") for t in [1.0, 1.1, 1.2, 1.5]]
    for r in ev_rows:
        print("  " + _fmt_roi(r, show_verdict=False))

    print("\n[探索: 妙味馬をオッズ帯で切る（人気薄は必要点数が跳ね上がる）]")
    bands = []
    for lo, hi in [(1, 3), (3, 6), (6, 12), (12, 30), (30, 1e9)]:
        m = (
            (oos["edge"] > PRIMARY_EDGE_THRESHOLD)
            & (oos["win_odds"].astype(float) >= lo)
            & (oos["win_odds"].astype(float) < hi)
        )
        bands.append(roi(m, f"edge>0 かつ {lo}〜{'∞' if hi > 1e8 else int(hi)}倍"))
    for r in bands:
        print("  " + _fmt_roi(r, show_verdict=False))

    print("\n[時系列: 主判定を年別／月別に割る（1つの時期に支えられていないか）]")
    sel = oos["edge"] > PRIMARY_EDGE_THRESHOLD
    yearly = [
        roi(sel & (oos["race_date"].dt.year == y), f"{y}年 edge>0")
        for y in sorted(oos["race_date"].dt.year.unique())
    ]
    for r in yearly:
        print("  " + _fmt_roi(r, show_verdict=False))
    month_key = oos["race_date"].dt.to_period("M").astype(str)
    monthly = [
        roi(sel & (month_key == m), f"{m} edge>0") for m in sorted(month_key.unique())
    ]
    print(
        f"  月別 {len(monthly)} 区間: "
        f"ROI 中央値 "
        f"{np.nanmedian([r['roi'] for r in monthly if r['roi'] is not None]) * 100:.1f}% / "
        f"100%超の月 "
        f"{sum(1 for r in monthly if r['roi'] and r['roi'] > 1.0)}/{len(monthly)} "
        f"（いずれも点数不足で単独では判定不能）"
    )

    results["roi"] = {
        "baselines": base,
        "model_naive": naive,
        "primary": primary,
        "exploratory_edge": explor,
        "exploratory_ev": ev_rows,
        "odds_bands": bands,
        "yearly": yearly,
        "monthly": monthly,
    }

    # ------------------------------------------------ 5. 判定
    _hr("5. 事前登録した基準による判定")
    # ⚠️ ゲートは生出力と正規化後の**厳しい方**で行う。正規化はレース内合計を
    #    1 に強制する＝「1着は必ず1頭」という真の制約を注入するので ECE を
    #    機械的に下げる。どちらでゲートするかは事前登録に書いていなかったので、
    #    甘い側を選ばないよう厳しい方に寄せる（security-reviewer M-2）。
    cal_ok = (
        cal["model_raw"]["calibration_ok"] and cal["model_normalized"]["calibration_ok"]
    )
    print(
        f"キャリブレーション: 生 ECE={cal['model_raw']['ece']:.4f} / "
        f"正規化後 ECE={cal['model_normalized']['ece']:.4f} "
        f"(許容 {ECE_TOLERANCE}, 厳しい方で判定) → "
        f"{'OK' if cal_ok else '🔴 崩れている'}"
    )
    print(
        f"  参考: 市場の ECE={cal['market_normalized']['ece']:.4f} "
        f"/ Brier 市場={cal['market_normalized']['brier']:.5f} "
        f"vs モデル={cal['model_normalized']['brier']:.5f}"
    )

    if primary["bets"] == 0:
        print("主判定: 対象0点（edge>0 の馬が1頭も無かった）")
    else:
        print(f"主判定 ROI: {primary['roi'] * 100:.1f}%  {primary['bets']:,}点")
        print(
            f"  CI95 = [{primary['ci95'][0] * 100:.1f}%, "
            f"{primary['ci95'][1] * 100:.1f}%]"
        )
    print(f"  判定 = {primary['verdict']}（{primary['verdict_reason']}）")

    # ⚠️ キャリブレーション不成立は「有意に赤字」ではない。事前登録 §2 の
    #    「見込みなし」に写すと ROI の情報が verdict から消えるため
    #    判定不能 + 理由 にする（code-reviewer M4）。
    if not cal_ok:
        final = VERDICT_UNDECIDABLE
        reason = (
            "キャリブレーションが許容を超えて崩れており、EV（期待値）ベースの"
            "戦略は現状成立しない。ROI の数値は参考値にとどまる"
            f"（参考: 主判定 ROI={primary['roi']}, 判定={primary['verdict']}）"
        )
    else:
        final = primary["verdict"]
        reason = primary["verdict_reason"]
    assert final in (VERDICT_YES, VERDICT_NO, VERDICT_UNDECIDABLE)

    print(f"\n🔴 最終判定: {final}\n   理由: {reason}")
    results["final_verdict"] = {
        "verdict": final,
        "reason": reason,
        "calibration_ok": bool(cal_ok),
    }

    out = Path(args.out)
    out.write_text(
        json.dumps(_json_safe(results), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(f"\nJSON: {out.resolve()}")
    print(f"models: {MODELS_DIR}")


if __name__ == "__main__":
    main()
