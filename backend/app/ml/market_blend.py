"""
二段モデル: 市場の確率にファンダメンタル予測を**足せるか**を検定する。

## なぜこれが必要だったか

2026-09-27 の最初の検証は「`p_model > p_market` の馬を買う」を測って否定した
（`docs/20260927-oddsfree-edge-results.md`）。しかしそれは
`logit(p) = 1·logit(p_model) − 1·logit(p_market)` と**重みを固定した特殊ケース**で、
「モデルは市場に情報を付け足せるか」という問いには答えていない。

Benter (1994) の方式は二段構え:

1. 市場の意見を見ずにファンダメンタル確率 `p_model` を作る
2. **重みをデータから学ぶ**:  `v_i = α·logit(p_model_i) + β·logit(p_market_i)`
   レース内で softmax して確率にする

決定的な検定は **α が 0 と区別できるか**。α ≈ 0 なら
「モデルは市場に何も足していない」が確定する。

## なぜ条件付きロジット（multinomial）なのか

競馬は「各レースでちょうど1頭が勝つ」構造を持つ。各馬を独立な二値事象として
扱うロジスティック回帰は、この制約を無視するため

- レース内の確率の合計が1にならない
- 標準誤差が過小になる（同一レース内の観測は独立でない）

条件付きロジット（= McFadden の離散選択モデル）は、レースを1観測として
「どの馬が勝ったか」の尤度を最大化するので、構造と一致する。

```
P(i が勝つ | レース r) = exp(v_i) / Σ_{j∈r} exp(v_j)
LL = Σ_r log P(勝ち馬_r)
```

⚠️ **切片 γ は条件付きロジットでは識別できない。** レース内で全馬に同じ値を
足しても softmax の結果は変わらないため、γ は尤度から消える。
（比較用に二値ロジスティック版も推定できるようにしてあり、そちらには切片が出る。
ただし上記の理由で標準誤差は信用できない。）
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import optimize, stats

logger = logging.getLogger(__name__)

#: logit を取る前に確率をこの範囲へ丸める。0 と 1 で ±inf になるのを防ぐ。
PROB_EPS = 1e-6


def logit(p: np.ndarray | pd.Series, eps: float = PROB_EPS) -> np.ndarray:
    """log(p / (1-p))。0/1 に張り付いた確率は eps で内側に丸める。"""
    arr = np.asarray(p, dtype="float64")
    clipped = np.clip(arr, eps, 1.0 - eps)
    return np.log(clipped / (1.0 - clipped))


def _race_codes(race_ids) -> tuple[np.ndarray, int]:
    codes, uniques = pd.factorize(pd.Series(race_ids), sort=False)
    if (codes < 0).any():
        raise ValueError("race_ids に欠損がある")
    return codes.astype("int64"), len(uniques)


def softmax_by_race(v: np.ndarray, codes: np.ndarray, n_races: int) -> np.ndarray:
    """レース内 softmax。オーバーフローを避けるためレースごとの最大値を引く。"""
    vmax = np.full(n_races, -np.inf, dtype="float64")
    np.maximum.at(vmax, codes, v)
    e = np.exp(v - vmax[codes])
    denom = np.bincount(codes, weights=e, minlength=n_races)
    return e / denom[codes]


def fit_conditional_logit(
    X: np.ndarray,
    race_ids,
    is_winner: np.ndarray,
    *,
    feature_names: list[str] | None = None,
) -> dict:
    """
    条件付きロジットを最大尤度で推定する。

    Args:
        X: (n_entries, n_features)。既に logit 変換済みの説明変数を渡すこと。
        race_ids: 行ごとのレース識別子。
        is_winner: 1着なら1。**各レースにちょうど1頭**であることを検査する。

    Returns:
        推定値・標準誤差・z値・p値・95%CI、対数尤度、疑似決定係数など。

    標準誤差は観測情報行列（＝条件付きロジットではフィッシャー情報量と一致）の
    逆行列から出す。1パラメータあたりの導出:

        ∂LL/∂θ = Σ_r ( x_勝ち馬 − Σ_j p_j x_j )
        I(θ)   = Σ_r ( Σ_j p_j x_j x_jᵀ − (Σ_j p_j x_j)(Σ_j p_j x_j)ᵀ )
               = Σ_r Cov_p(x)

    ⚠️ **レース内分散が無い説明変数は識別できない。** 例えば全馬で同じ値を
       取る列（切片を含む）は Cov_p が 0 になり、情報行列が特異になる。
    """
    X = np.asarray(X, dtype="float64")
    if X.ndim != 2:
        raise ValueError("X は2次元で渡すこと")
    y = np.asarray(is_winner, dtype="float64")
    if len(y) != len(X):
        raise ValueError(f"長さ不一致: X={len(X)} y={len(y)}")

    codes, n_races = _race_codes(race_ids)
    wins_per_race = np.bincount(codes, weights=y, minlength=n_races)
    if not np.allclose(wins_per_race, 1.0):
        bad = int((~np.isclose(wins_per_race, 1.0)).sum())
        raise ValueError(
            f"勝ち馬がちょうど1頭でないレースが {bad} 件ある。"
            "同着や未確定を呼び出し側で除いてから渡すこと"
        )

    k = X.shape[1]
    names = feature_names or [f"x{i}" for i in range(k)]

    # ⚠️ 目的関数は**レース平均**にする。合計のままだと勾配の大きさが n に比例し、
    #    絶対値ベースの `gtol` に到達できず `converged=False` になる（実測）。
    #    推定値は同じで、収束判定だけがスケール非依存になる。
    #    情報行列は合計スケールで別に計算する（標準誤差は合計スケールが正しい）。
    def neg_ll_and_grad(theta: np.ndarray) -> tuple[float, np.ndarray]:
        v = X @ theta
        p = softmax_by_race(v, codes, n_races)
        ll = float(np.sum(y * np.log(np.clip(p, 1e-300, None))))
        grad = X.T @ (y - p)  # Σ_r (x_勝ち馬 − Σ_j p_j x_j)
        return -ll / n_races, -grad / n_races

    res = optimize.minimize(
        neg_ll_and_grad,
        x0=np.zeros(k),
        jac=True,
        method="BFGS",
        options={"maxiter": 1000, "gtol": 1e-9},
    )
    theta = res.x
    v = X @ theta
    p = softmax_by_race(v, codes, n_races)

    # フィッシャー情報量 = Σ_r Cov_p(x)
    info = np.zeros((k, k))
    means = np.column_stack(
        [np.bincount(codes, weights=p * X[:, a], minlength=n_races) for a in range(k)]
    )
    for a in range(k):
        for b in range(k):
            second = np.bincount(
                codes, weights=p * X[:, a] * X[:, b], minlength=n_races
            )
            info[a, b] = float(np.sum(second - means[:, a] * means[:, b]))

    try:
        cov = np.linalg.inv(info)
        se = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        cov = None
        se = np.full(k, np.nan)

    # 完全分離（separation）だと係数が発散するが BFGS は「収束」と報告する。
    # 実測で theta=[-10.45, 7.4e-17] / converged=True になる例があった
    # （code-reviewer 指摘）。SE が意味を失ったまま有意に見えるのを防ぐ。
    diverged = bool(np.max(np.abs(theta)) > 50.0)

    ll = float(np.sum(y * np.log(np.clip(p, 1e-300, None))))
    # 帰無モデル = レース内一様（各馬 1/頭数）
    size = np.bincount(codes, minlength=n_races).astype("float64")
    ll_null = float(-np.sum(np.log(size)))

    z = theta / se
    pvals = 2.0 * stats.norm.sf(np.abs(z))
    lo = theta - 1.959964 * se
    hi = theta + 1.959964 * se

    coefs = {
        name: {
            "estimate": float(theta[i]),
            "std_error": float(se[i]),
            "z": float(z[i]),
            "p_value": float(pvals[i]),
            "ci95": (float(lo[i]), float(hi[i])),
            "significant_at_5pct": bool(pvals[i] < 0.05),
        }
        for i, name in enumerate(names)
    }

    return {
        "coefficients": coefs,
        "log_likelihood": ll,
        "log_likelihood_null": ll_null,
        "mcfadden_r2": float(1.0 - ll / ll_null) if ll_null != 0 else None,
        "n_entries": int(len(y)),
        "n_races": int(n_races),
        "converged": bool(res.success) and not diverged,
        "diverged": diverged,
        "optimizer_message": str(res.message),
        "theta": theta.tolist(),
        "feature_names": names,
    }


def blend_probabilities(
    X: np.ndarray, race_ids, theta: np.ndarray | list[float]
) -> np.ndarray:
    """推定した係数でレース内正規化済みの確率を作る。"""
    X = np.asarray(X, dtype="float64")
    codes, n_races = _race_codes(race_ids)
    return softmax_by_race(X @ np.asarray(theta, dtype="float64"), codes, n_races)


def race_log_loss(prob: np.ndarray, race_ids, is_winner: np.ndarray) -> float:
    """
    レースを1観測とした対数損失（= −平均 log P(勝ち馬)）。低いほど良い。

    ⚠️ 馬ごとの二値 log loss は使わない。ハズレ馬が圧倒的に多いため、
       「全馬に低い確率を出すだけ」で良く見えてしまう。
    """
    p = np.asarray(prob, dtype="float64")
    y = np.asarray(is_winner, dtype="float64")
    codes, n_races = _race_codes(race_ids)

    # ⚠️ `fit_conditional_logit` と同じ前提（各レース勝ち馬ちょうど1頭）を
    #    ここでも検査する。無検査だと壊れた入力で**静かに誤答する**:
    #      勝ち馬0頭 → log(1e-300)=690 が平均に混ざり指標を破壊
    #      同着2頭   → 2頭の確率を足した値を返す（例外も警告も出ない）
    #    log loss はモデル比較＝金銭判断に使うので、静かに逆転されるのが最悪
    #    （code-reviewer が実測して指摘）。
    wins_per_race = np.bincount(codes, weights=y, minlength=n_races)
    if not np.allclose(wins_per_race, 1.0):
        bad = int((~np.isclose(wins_per_race, 1.0)).sum())
        raise ValueError(
            f"勝ち馬がちょうど1頭でないレースが {bad} 件ある。"
            "同着や未確定を呼び出し側で除いてから渡すこと"
        )

    winner_p = np.bincount(codes, weights=y * p, minlength=n_races)
    return float(-np.mean(np.log(np.clip(winner_p, 1e-300, None))))


def fit_binary_logistic(X: np.ndarray, is_winner: np.ndarray) -> dict:
    """
    比較用の**二値**ロジスティック回帰（切片あり）。

    🔴 **本筋ではない。** 各馬を独立事象として扱うため
       「各レースでちょうど1頭が勝つ」制約を無視する。結果として:

       - レース内の確率の合計が1にならない
       - 同一レース内の観測が独立でないため **標準誤差が過小**になり、
         p値が実際より小さく（有意に見えやすく）出る

       切片が推定できるのはこちらだけなので、条件付きロジットで
       識別できない γ の目安を見るためだけに使う。
    """
    from sklearn.linear_model import LogisticRegression

    X = np.asarray(X, dtype="float64")
    y = np.asarray(is_winner, dtype="float64")
    clf = LogisticRegression(C=np.inf, max_iter=1000)
    clf.fit(X, y)
    return {
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "caveat": (
            "二値ロジスティックはレース内の1頭制約を無視するため、"
            "標準誤差が過小で p 値は信用できない。係数の符号と大きさの目安のみ"
        ),
    }
