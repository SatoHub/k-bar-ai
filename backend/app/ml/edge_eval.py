"""
「オッズ非依存モデルは市場より優れた確率を出せているか」を測る評価器。

🔴 **このモジュールの出力は金銭の判断に使われる。** 甘い数字を出す実装は
そのまま損失になるので、以下を設計上の規約とする。

1. 損益分岐は **ROI = 1.00**。控除率 0.80 は「無策で賭けた時の期待値」であって
   分岐点ではない（2026-09-27 に `verifier.py` で同じ取り違えをレビュー3件で指摘された）。
2. **点数が足りなければ「判定不能」を返す。** ROI が 100% を超えていても、
   精度要件を満たさなければ「見込みあり」とは言わない。
3. 単勝の1点あたり収支は裾が重い（実測 sd = 1.08〜8.66、オッズ帯で65倍違う）。
   正規近似を信用せず **bootstrap CI** を主に使う。

判定基準の全文と根拠は `docs/20260927-oddsfree-edge-criteria.md`（測定前に確定）。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --- 事前登録した定数（docs/20260927-oddsfree-edge-criteria.md）---
BREAKEVEN_ROI = 1.0
#: 95% CI の半幅がこれを超えたら精度不足と見なす
CI_HALFWIDTH_TARGET = 0.10
#: sd がどれだけ小さくてもこの点数を下回ったら判定しない
MIN_BETS = 500
#: キャリブレーション誤差がこれを超えたら EV 戦略は成立しないと結論する
ECE_TOLERANCE = 0.02
BOOTSTRAP_SAMPLES = 10_000
Z95 = 1.959964

VERDICT_YES = "見込みあり"
VERDICT_NO = "見込みなし"
VERDICT_UNDECIDABLE = "判定不能"


# ---------------------------------------------------------------- 市場確率
def market_implied_prob(
    win_odds: pd.Series,
    race_ids: pd.Series,
    *,
    method: str = "normalized",
) -> pd.Series:
    """
    単勝オッズから「市場が考える勝率」を復元する。

    Args:
        method:
            ``"normalized"`` … レース内で ``(1/O) / Σ(1/O)``。オーバーラウンド
                (控除率による合計>1) をレース単位で正しく除去する。**既定。**
            ``"takeout"``   … ``(1 - 控除率) / O``。控除率を全レース共通の定数と
                みなす近似。レースごとの実際のオーバーラウンドのばらつきを無視する。

    ⚠️ ``normalized`` はレース内合計が厳密に 1 になるため、
       「1着馬は必ず1頭」という制約と整合する。``takeout`` は整合しない。
    """
    odds = pd.to_numeric(win_odds, errors="coerce").astype("float64")
    inv = 1.0 / odds.where(odds > 0)

    if method == "normalized":
        denom = inv.groupby(race_ids).transform("sum")
        return inv / denom.where(denom > 0)
    if method == "takeout":
        # 実測の控除率 (docs の Σ(1/odds)=1.2529 → 1/1.2529)
        return inv / 1.2529
    raise ValueError(f"unknown method: {method}")


def normalize_within_race(prob: pd.Series, race_ids: pd.Series) -> pd.Series:
    """
    二値分類の出力はレース内で合計 1 にならないので正規化する。

    ⚠️ 正規化しないままモデル確率と市場確率を比べると、モデル全体の水準の
       ずれ（例: 常に高めに出る）が全頭のエッジに一律に乗り、
       「全馬に妙味がある」という無意味な結果になる。
    """
    p = pd.to_numeric(prob, errors="coerce").astype("float64")
    denom = p.groupby(race_ids).transform("sum")
    return p / denom.where(denom > 0)


# ------------------------------------------------------- キャリブレーション
def calibration(
    prob: np.ndarray | pd.Series,
    actual: np.ndarray | pd.Series,
    *,
    n_bins: int = 10,
) -> dict:
    """
    信頼度曲線と ECE / Brier を返す。

    「勝率20%と言った馬が実際に20%勝っているか」。EV 判定はここが崩れていると
    成立しないため、ROI より先に確認する。

    ビン分割は**等頻度（分位）**にする。単勝の予測確率は 0 付近に密集するので
    等幅ビンでは大半が1つのビンに入り、曲線が読めなくなる。
    """
    p = np.asarray(prob, dtype="float64")
    y = np.asarray(actual, dtype="float64")
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]

    def _result(bins: list, ece: float | None, brier: float | None, n: int) -> dict:
        # ⚠️ 返り値の形は常に同じにする。異常系で `calibration_ok` が欠けると
        #    呼び出し側が KeyError で落ちる（テストで検出した）。
        return {
            "bins": bins,
            "ece": ece,
            "brier": brier,
            "n": n,
            "ece_tolerance": ECE_TOLERANCE,
            "calibration_ok": bool(ece is not None and ece <= ECE_TOLERANCE),
        }

    if len(p) == 0:
        return _result([], None, None, 0)

    brier = float(np.mean((p - y) ** 2))

    # 分位ビン。同値が多いと境界が縮退するので unique を取る
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 2:
        # 予測が全て同値（定数を吐く壊れたモデル）。捨てずに1ビンとして扱う。
        # ここで空を返すと「キャリブレーションが測れない」ことが
        # 「問題なし」として通過してしまう。
        idx = np.zeros(len(p), dtype="int64")
        edges = np.array([edges[0], edges[0]])
        n_actual_bins = 1
    else:
        idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
        n_actual_bins = len(edges) - 1

    bins, ece = [], 0.0
    for b in range(n_actual_bins):
        m = idx == b
        cnt = int(m.sum())
        if cnt == 0:
            continue
        pred, act = float(p[m].mean()), float(y[m].mean())
        bins.append(
            {
                "bin": b,
                "range": (float(edges[b]), float(edges[b + 1])),
                "count": cnt,
                "mean_predicted": pred,
                "actual_rate": act,
                "gap": pred - act,
            }
        )
        ece += cnt / len(p) * abs(pred - act)

    return _result(bins, float(ece), brier, int(len(p)))


# ------------------------------------------------------------------ ROI
def bootstrap_ci(
    payoffs: np.ndarray,
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = 42,
    chunk: int = 200,
) -> tuple[float, float]:
    """
    平均（=ROI）の 95% percentile bootstrap CI。

    単勝の払戻分布は裾が重く、正規近似は CI の端で信用できない。
    メモリを食わないようチャンクに割って回す。
    """
    n = len(payoffs)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype="float64")
    done = 0
    while done < samples:
        k = min(chunk, samples - done)
        idx = rng.integers(0, n, size=(k, n))
        means[done : done + k] = payoffs[idx].mean(axis=1)
        done += k
    return (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))


def required_bets(sd: float, halfwidth: float = CI_HALFWIDTH_TARGET) -> float:
    """CI 半幅を ``halfwidth`` 以内にするのに必要な点数（正規近似の逆算）。"""
    if not np.isfinite(sd):
        return float("nan")
    return float((Z95 * sd / halfwidth) ** 2)


def roi_summary(
    win_odds: pd.Series | np.ndarray,
    is_winner: pd.Series | np.ndarray,
    *,
    label: str = "",
    seed: int = 42,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict:
    """
    フラット（均等）ベットでの単勝 ROI と、事前登録した基準による判定を返す。

    1点あたりの収支 ``X = オッズ × 当たり(0/1)``。ROI は ``mean(X)``
    （賭け金1単位あたりの払戻）。**1.00 が損益分岐。**
    """
    odds = pd.to_numeric(pd.Series(win_odds).reset_index(drop=True), errors="coerce")
    won = pd.Series(is_winner).reset_index(drop=True).astype("float64")
    ok = odds.notna() & (odds > 0) & won.notna()
    odds, won = odds[ok].to_numpy(dtype="float64"), won[ok].to_numpy(dtype="float64")

    n = int(len(odds))
    if n == 0:
        return {
            "label": label,
            "bets": 0,
            "hit_rate": None,
            "roi": None,
            "verdict": VERDICT_UNDECIDABLE,
            "verdict_reason": "対象0点",
        }

    payoffs = odds * won
    roi = float(payoffs.mean())
    sd = float(payoffs.std(ddof=1)) if n > 1 else float("nan")
    ci_lo, ci_hi = bootstrap_ci(payoffs, samples=bootstrap_samples, seed=seed)
    half = (ci_hi - ci_lo) / 2.0
    normal_se = sd / np.sqrt(n) if np.isfinite(sd) else float("nan")
    need = required_bets(sd)

    # --- 事前登録した判定（docs/20260927-oddsfree-edge-criteria.md §2）---
    if n < MIN_BETS:
        verdict, reason = VERDICT_UNDECIDABLE, f"点数不足 ({n} < {MIN_BETS})"
    elif not np.isfinite(half) or half > CI_HALFWIDTH_TARGET:
        verdict = VERDICT_UNDECIDABLE
        reason = (
            f"精度不足 (CI半幅 {half:.3f} > {CI_HALFWIDTH_TARGET}; "
            f"必要 {need:,.0f}点 に対し {n:,}点)"
        )
    elif ci_lo > BREAKEVEN_ROI:
        verdict, reason = VERDICT_YES, f"CI下限 {ci_lo:.3f} > {BREAKEVEN_ROI}"
    elif ci_hi < BREAKEVEN_ROI:
        verdict, reason = VERDICT_NO, f"CI上限 {ci_hi:.3f} < {BREAKEVEN_ROI}"
    else:
        verdict = VERDICT_UNDECIDABLE
        reason = f"CI [{ci_lo:.3f}, {ci_hi:.3f}] が {BREAKEVEN_ROI} をまたぐ"

    return {
        "label": label,
        "bets": n,
        "hit_rate": float(won.mean()),
        "roi": roi,
        "payoff_sd": sd,
        "ci95": (ci_lo, ci_hi),
        "ci_halfwidth": float(half),
        "normal_se": float(normal_se),
        "required_bets_for_target": need,
        "mean_odds": float(odds.mean()),
        "median_odds": float(np.median(odds)),
        "is_profitable_point_estimate": roi > BREAKEVEN_ROI,
        "verdict": verdict,
        "verdict_reason": reason,
    }
