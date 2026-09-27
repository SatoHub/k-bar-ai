"""
Benter 流の二段モデルで「モデルは市場の確率に情報を**足せるか**」を検定する。

問いの立て方が前回と違う。前回（`scripts/oddsfree_edge_eval.py`）は
`p_model > p_market` の馬を買う戦略を測って否定したが、それは
`logit = 1·logit(p_model) − 1·logit(p_market)` と**重みを固定した特殊ケース**。
ここでは重みをデータから学ぶ。

    v_i = α·logit(p_model_i) + β·logit(p_market_i)
    P(i が勝つ) = exp(v_i) / Σ_{j∈同レース} exp(v_j)

**決定的な検定は α が 0 と区別できるか。** α ≈ 0 なら
「モデルは市場に何も足していない」が最終確定する。

時系列の分け方（3段すべて別期間にする）:

    stage1 (oddsfree モデル)  : 2019年以前で学習（既に済み）
    stage2 (α, β の推定)      : 2020年
    評価 (log loss / ROI)     : 2021年以降

⚠️ α が有意でも、それは「市場に情報を足せる」までしか意味しない。
   **「儲かる」は別問題**（控除率20%の壁）。両者を分けて報告する。

出力は標準出力と JSON。**DB への書き込みは行わない。**

実行:
    cd backend && PYTHONPATH=. uv run python scripts/market_blend_eval.py
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
from sklearn.metrics import brier_score_loss, roc_auc_score

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.edge_eval import (  # noqa: E402
    ECE_TOLERANCE,
    VERDICT_UNDECIDABLE,
    calibration,
    market_implied_prob,
    normalize_within_race,
    roi_summary,
)
from app.ml.features import build_feature_matrix  # noqa: E402
from app.ml.market_blend import (  # noqa: E402
    blend_probabilities,
    fit_binary_logistic,
    fit_conditional_logit,
    logit,
    race_log_loss,
)
from app.ml.oddsfree import load_oddsfree  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("market_blend_eval")

#: stage1 の学習カットオフ（ここより前で oddsfree を学習済み）
STAGE1_CUTOFF_YEAR = 2020
#: stage2（α,β の推定）に使う期間。ここも stage1 から見れば out-of-sample。
STAGE2_YEARS = [2020]
#: 最終評価に使う期間。stage1 も stage2 も見ていない。
EVAL_START = "2021-01-01"
#: 主判定の閾値は既存の事前登録（docs/20260927-oddsfree-edge-criteria.md）を流用する。
PRIMARY_EDGE_THRESHOLD = 0.0
EXPLORATORY_LABEL = "探索(判定根拠外)"


def _hr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def _fmt_roi(r: dict, *, show_verdict: bool = True) -> str:
    if r["bets"] == 0:
        return f"{r['label']:<36} 対象0点"
    lo, hi = r["ci95"]
    tail = r["verdict"] if show_verdict else EXPLORATORY_LABEL
    return (
        f"{r['label']:<36} {r['bets']:>7,}点 "
        f"的中{r['hit_rate'] * 100:>5.1f}% ROI {r['roi'] * 100:>6.1f}% "
        f"CI[{lo * 100:>6.1f},{hi * 100:>6.1f}] "
        f"必要{r['required_bets_for_target']:>9,.0f}点 "
        f"平均{r['mean_odds']:>6.1f}倍  {tail}"
    )


def _json_safe(o):
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def _print_coefs(res: dict) -> None:
    print(
        f"  収束: {res['converged']} ({res['optimizer_message']})\n"
        f"  レース数 {res['n_races']:,} / 出走 {res['n_entries']:,}\n"
        f"  対数尤度 {res['log_likelihood']:.2f} "
        f"(一様モデル {res['log_likelihood_null']:.2f}) "
        f"McFadden R² = {res['mcfadden_r2']:.4f}"
    )
    print(
        f"\n  {'係数':<26}{'推定値':>10}{'標準誤差':>10}{'z':>9}"
        f"{'p値':>12}{'95%CI':>24}"
    )
    for name, c in res["coefficients"].items():
        print(
            f"  {name:<26}{c['estimate']:>10.4f}{c['std_error']:>10.4f}"
            f"{c['z']:>9.2f}{c['p_value']:>12.3e}"
            f"   [{c['ci95'][0]:>8.4f}, {c['ci95'][1]:>8.4f}]"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="market_blend_eval.json")
    args = ap.parse_args()
    results: dict = {
        "criteria_doc": "docs/20260927-oddsfree-edge-criteria.md",
        "design": {
            "stage1_train": f"< {STAGE1_CUTOFF_YEAR}",
            "stage2_fit": STAGE2_YEARS,
            "eval_from": EVAL_START,
        },
    }

    # ------------------------------------------------------------ 0. データ
    _hr("0. データ準備")
    art = load_oddsfree("v1.2.0_win")
    if art.get("target_column") != "is_win" or art.get("cutoff_year") != 2020:
        raise SystemExit(
            f"想定と違う artifact: target={art.get('target_column')} "
            f"cutoff={art.get('cutoff_year')}"
        )
    feats = art["feature_columns"]
    print(
        f"stage1 モデル: v1.2.0_win_oddsfree "
        f"(target=is_win / cutoff=2020 / {len(feats)}特徴量 / "
        f"学習 {art['created_at'][:19]} / test AUC "
        f"{art['metrics']['roc_auc']:.5f})"
    )

    # 非完走馬を落とさない（前回の codex 指摘と同じ理由）
    full = build_feature_matrix(include_upcoming=True)
    df = full[full["race_date"].dt.year >= STAGE1_CUTOFF_YEAR].copy()
    del full
    raced = df.groupby("race_id_str")["finish_position"].transform("count") > 0
    df = df[raced]
    df = df[df["win_odds"].notna() & (df["win_odds"].astype(float) > 0)].copy()
    df = df.reset_index(drop=True)
    df["is_win"] = (df["finish_position"] == 1).fillna(False).astype("float64")

    df["p_model"] = normalize_within_race(
        pd.Series(art["model"].predict(df[feats]), index=df.index), df["race_id_str"]
    )
    df["p_market"] = market_implied_prob(
        df["win_odds"], df["race_id_str"], method="normalized"
    )
    n_before = len(df)
    df = df[df["p_model"].notna() & df["p_market"].notna()].copy()

    # 🔴 条件付きロジットは「各レースちょうど1頭が勝つ」を要求する。
    #    同着1着や、勝ち馬の行が落ちたレースは**除外して件数を記録する**
    #    （黙って混ぜると尤度が壊れる）。
    wins = df.groupby("race_id_str")["is_win"].transform("sum")
    ok_races = wins == 1.0
    n_bad_races = int(df.loc[~ok_races, "race_id_str"].nunique())
    df = df[ok_races].reset_index(drop=True)
    print(
        f"{len(df):,} 行 / {df['race_id_str'].nunique():,} レース "
        f"({df['race_date'].min().date()} 〜 {df['race_date'].max().date()})\n"
        f"  確率NaNで除外: {n_before - len(df) - int((~ok_races).sum()):,}\n"
        f"  勝ち馬が1頭でないレースを除外: {n_bad_races:,} レース"
    )

    df["x_model"] = logit(df["p_model"])
    df["x_market"] = logit(df["p_market"])
    X_cols = ["x_model", "x_market"]
    NAMES = ["alpha_model", "beta_market"]

    stage2 = df[df["race_date"].dt.year.isin(STAGE2_YEARS)].copy()
    evald = df[df["race_date"] >= pd.Timestamp(EVAL_START)].copy()
    print(
        f"  stage2(推定): {len(stage2):,}行 / {stage2['race_id_str'].nunique():,}レース\n"
        f"  評価:         {len(evald):,}行 / {evald['race_id_str'].nunique():,}レース "
        f"({evald['race_date'].min().date()} 〜 {evald['race_date'].max().date()})"
    )
    results["samples"] = {
        "stage2_races": int(stage2["race_id_str"].nunique()),
        "eval_races": int(evald["race_id_str"].nunique()),
        "eval_entries": int(len(evald)),
        "excluded_races_not_exactly_one_winner": n_bad_races,
    }

    # ------------------------------------------- 1. 条件付きロジットの推定
    _hr("1. 🔴 決定的な検定: α（モデルの寄与）はゼロと区別できるか")
    print("推定期間: 2020年（stage1 の学習期間 2019年以前とは別期間）\n")
    fit = fit_conditional_logit(
        stage2[X_cols].to_numpy(),
        stage2["race_id_str"],
        stage2["is_win"].to_numpy(),
        feature_names=NAMES,
    )
    _print_coefs(fit)
    a = fit["coefficients"]["alpha_model"]
    alpha_significant = bool(a["p_value"] < 0.05 and a["ci95"][0] > 0)
    print(
        f"\n  → α {'は 0 と区別できる（有意）' if alpha_significant else 'は 0 と区別できない'}"
        f"  p={a['p_value']:.3e} / 95%CI=[{a['ci95'][0]:.4f}, {a['ci95'][1]:.4f}]"
    )
    results["stage2_conditional_logit"] = fit
    results["alpha_significant"] = alpha_significant

    # 市場だけのモデル（α を強制的に 0 にした場合）との尤度比検定
    market_only = fit_conditional_logit(
        stage2[["x_market"]].to_numpy(),
        stage2["race_id_str"],
        stage2["is_win"].to_numpy(),
        feature_names=["beta_market"],
    )
    from scipy import stats as _st

    lr_stat = 2.0 * (fit["log_likelihood"] - market_only["log_likelihood"])
    lr_p = float(_st.chi2.sf(lr_stat, df=1))
    print(
        f"\n  尤度比検定（市場のみ vs 市場+モデル）: "
        f"LR={lr_stat:.2f} (自由度1) p={lr_p:.3e}"
    )
    results["likelihood_ratio_test"] = {
        "statistic": float(lr_stat),
        "df": 1,
        "p_value": lr_p,
        "market_only_log_likelihood": market_only["log_likelihood"],
    }

    # 参考: 二値ロジスティック（切片が出るのはこちらだけ。ただし SE は信用不可）
    binlog = fit_binary_logistic(stage2[X_cols].to_numpy(), stage2["is_win"].to_numpy())
    print(
        f"\n  [参考] 二値ロジスティック: α={binlog['coef'][0]:.4f} "
        f"β={binlog['coef'][1]:.4f} γ(切片)={binlog['intercept']:.4f}\n"
        f"    ⚠️ {binlog['caveat']}\n"
        f"    ⚠️ 条件付きロジットでは γ は識別できない"
        f"（レース内で全馬に同じ値を足しても softmax は変わらないため）"
    )
    results["binary_logistic_reference"] = binlog

    # ------------------------------------------- 2. out-of-sample 予測精度
    _hr("2. out-of-sample の予測精度（2021年以降・stage2 の推定に使っていない期間）")
    theta = fit["theta"]
    evald["p_blend"] = blend_probabilities(
        evald[X_cols].to_numpy(), evald["race_id_str"], theta
    )
    evald["p_market_only"] = blend_probabilities(
        evald[["x_market"]].to_numpy(),
        evald["race_id_str"],
        market_only["theta"],
    )

    rows = []
    for name, col in [
        ("市場のみ（β再推定・正規化後）", "p_market_only"),
        ("市場の生オッズ確率", "p_market"),
        ("モデルのみ", "p_model"),
        ("**結合モデル**", "p_blend"),
    ]:
        p = evald[col].to_numpy()
        y = evald["is_win"].to_numpy()
        rows.append(
            {
                "name": name,
                "race_log_loss": race_log_loss(p, evald["race_id_str"], y),
                "brier": float(brier_score_loss(y, np.clip(p, 0, 1))),
                "auc": float(roc_auc_score(y, p)),
                "ece": calibration(p, y)["ece"],
            }
        )
    print(
        f"  {'手法':<30}{'レース対数損失':>16}{'Brier':>10}{'AUC':>9}{'ECE':>9}\n"
        f"  {'（低いほど良い）':<30}{'↓':>16}{'↓':>10}{'↑':>9}{'↓':>9}"
    )
    for r in rows:
        print(
            f"  {r['name']:<30}{r['race_log_loss']:>16.5f}{r['brier']:>10.5f}"
            f"{r['auc']:>9.4f}{r['ece']:>9.4f}"
        )
    base = next(r for r in rows if r["name"] == "市場のみ（β再推定・正規化後）")
    blend = next(r for r in rows if r["name"] == "**結合モデル**")
    d_ll = base["race_log_loss"] - blend["race_log_loss"]
    print(f"\n  結合モデルの対数損失の改善: {d_ll:+.5f}（正なら結合が優れている）")
    results["out_of_sample_metrics"] = rows
    results["log_loss_improvement_vs_market_only"] = float(d_ll)

    # ------------------------------------------- 3. 経済的価値
    _hr("3. 経済的価値（α が有意だった場合のみ意味を持つ）")
    if not alpha_significant:
        print(
            "α が 0 と区別できないため、期待値ベースの戦略は成立しない。\n"
            "参考値として ROI は出すが、判定には使わない。"
        )
    evald["edge_blend"] = evald["p_blend"] - evald["p_market"]
    evald["ev_blend"] = evald["p_blend"] * evald["win_odds"].astype(float)

    def roi(mask, label: str) -> dict:
        s = evald if mask is None else evald[mask]
        return roi_summary(s["win_odds"], s["is_win"], label=label)

    print("\n[ベースライン（同一期間・同一集合）]")
    for r in [
        roi(None, "全馬均等買い"),
        roi(
            evald.index.isin(evald.groupby("race_id_str")["p_market"].idxmax()),
            "市場最上位1頭",
        ),
    ]:
        print("  " + _fmt_roi(r))

    print(f"\n[🔴 主判定: 結合モデルの edge > {PRIMARY_EDGE_THRESHOLD}]")
    primary = roi(evald["edge_blend"] > PRIMARY_EDGE_THRESHOLD, "結合 edge>0")
    print("  " + _fmt_roi(primary))

    print("\n[探索: 期待値 EV = 結合確率 × オッズ]")
    ev_rows = [roi(evald["ev_blend"] > t, f"EV>{t:.2f}") for t in [1.0, 1.05, 1.1, 1.2]]
    for r in ev_rows:
        print("  " + _fmt_roi(r, show_verdict=False))

    print("\n[探索: オッズ帯別（人気帯は検証可能・人気薄は構造的に判定不能）]")
    bands = []
    for lo, hi in [(1, 3), (3, 6), (6, 12), (12, 30), (30, 1e9)]:
        m = (
            (evald["edge_blend"] > PRIMARY_EDGE_THRESHOLD)
            & (evald["win_odds"].astype(float) >= lo)
            & (evald["win_odds"].astype(float) < hi)
        )
        bands.append(roi(m, f"edge>0 かつ {lo}〜{'∞' if hi > 1e8 else int(hi)}倍"))
    for r in bands:
        print("  " + _fmt_roi(r, show_verdict=False))
    results["roi"] = {"primary": primary, "ev": ev_rows, "odds_bands": bands}

    # ------------------------------------------- 4. 最終判定
    _hr("4. 最終判定")
    print(
        f"問い1「モデルは市場に情報を足せるか」: "
        f"{'✅ 足せる' if alpha_significant else '❌ 足せない'}\n"
        f"  α = {a['estimate']:.4f} (SE {a['std_error']:.4f}) "
        f"p = {a['p_value']:.3e} 95%CI [{a['ci95'][0]:.4f}, {a['ci95'][1]:.4f}]\n"
        f"  out-of-sample の対数損失改善 = {d_ll:+.5f}"
    )
    if alpha_significant:
        econ = primary["verdict"]
        econ_reason = primary["verdict_reason"]
    else:
        econ = VERDICT_UNDECIDABLE
        econ_reason = (
            "α が 0 と区別できないため、期待値ベースの戦略の前提が成立しない"
            f"（参考: 主判定 ROI={primary['roi']}, {primary['verdict']}）"
        )
    print(f"\n問い2「儲かるか」: {econ}\n  理由: {econ_reason}")
    print(
        "\n⚠️ 限界（必ず併記する）:\n"
        "  - 確定オッズで採点している。実運用では締切前オッズしか使えないため、\n"
        "    ここで測った ROI は**現実より楽観的**\n"
        "  - 評価期間は 2021年以降のみ。前回の 5,585レースより小さい\n"
        "  - 複勝以降は払戻オッズが DB に無く評価不能"
    )
    results["final"] = {
        "adds_information": alpha_significant,
        "economic_verdict": econ,
        "economic_reason": econ_reason,
        "ece_tolerance": ECE_TOLERANCE,
    }

    out = Path(args.out)
    out.write_text(
        json.dumps(_json_safe(results), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(f"\nJSON: {out.resolve()}")


if __name__ == "__main__":
    main()
