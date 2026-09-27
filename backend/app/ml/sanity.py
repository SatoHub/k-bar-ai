"""
学習済みモデルのサニティチェック。

**何のためにあるか**
2026-09-27 に、集計特徴量24個が `rolling`/`expanding` を groupby の外で
呼んでいたため「別のエンティティの値を拾う」バグが見つかった。
うち12個は実質「データ全体の累積平均」で、騎手・調教師固有の情報を
ほとんど持っていなかった。それでも accuracy / AUC は出ていたため、
**指標を見るだけでは壊れていることに気づけなかった。**

そこで「モデルが本当は何に依存しているのか」を暴く検査を評価時に常設する。

- `permutation_auc_drop`: 特徴量を1つずつシャッフルして AUC の低下を測る。
  低下がほぼ 0 の特徴量は **実質機能していない**（壊れている / 無意味）。
- `odds_dependency`: オッズ関連の特徴量だけをシャッフルして AUC の低下を測る。
  低下が大きいほど「市場の意見をなぞっているだけ」で、独自の情報が薄い。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)

# 市場（オッズ・人気）由来の特徴量。ここへの依存度が高いほど独自情報が薄い。
MARKET_FEATURES = ["win_odds", "win_favorite"]

# 「実質機能していない」の判定。絶対値と相対値の**大きい方**を閾値にする。
#
# 絶対値だけでは足りない: モデルがノイズ列に過適合していると、無意味な列でも
# シャッフルで AUC が動く（テストで実測: 合成データでノイズ列が 0.0226 低下）。
# 逆に相対値だけでも足りない: 全特徴量が弱いと最大値自体が小さく基準が崩れる。
DEAD_FEATURE_AUC_DROP = 0.0005
DEAD_FEATURE_RELATIVE = 0.01  # 最大低下量に対する比

# シャッフルは乱数なので1回だと揺れる。複数シードで平均する。
PERMUTATION_REPEATS = 3


def _auc(booster, X: pd.DataFrame, y: np.ndarray) -> float:
    return float(roc_auc_score(y, booster.predict(X)))


def permutation_auc_drop(
    booster,
    X: pd.DataFrame,
    y: np.ndarray,
    *,
    seed: int = 42,
) -> dict[str, float]:
    """
    特徴量を1つずつシャッフルして AUC の低下量を返す（大きいほど重要）。

    SHAP の重要度は「モデルが何を見ているか」を示すが、
    **その特徴量が正しく計算されているか**は示さない。
    シャッフルして性能が落ちないなら、その特徴量は実質使われていない。
    """
    base = _auc(booster, X, y)
    drops: dict[str, float] = {}
    # フレーム全体のコピーはループ外で1回だけ。中で毎回 copy すると
    # 特徴量数 × PERMUTATION_REPEATS 回（本番で123回）の全件コピーになる。
    shuffled = X.copy()
    for col in X.columns:
        original = shuffled[col]
        # 1回のシャッフルだと乱数の揺れで順位が入れ替わるため平均を取る
        total = 0.0
        for r in range(PERMUTATION_REPEATS):
            rng = np.random.default_rng(seed + r)
            # ⚠️ `rng.permutation(series.to_numpy())` で代入してはいけない。
            #    categorical 列の dtype が落ち、LightGBM が
            #    "train and valid dataset categorical_feature do not match"
            #    で例外を投げる（本番は surface / track_condition 等6列が
            #    categorical。codex レビューで検出し実測で再現）。
            #    位置シャッフル + set_axis なら dtype と categories を保てる。
            order = rng.permutation(len(shuffled))
            shuffled[col] = original.iloc[order].set_axis(shuffled.index)
            total += base - _auc(booster, shuffled, y)
        drops[col] = total / PERMUTATION_REPEATS
        shuffled[col] = original  # 次の列に進む前に必ず戻す
    return drops


def odds_dependency(
    booster,
    X: pd.DataFrame,
    y: np.ndarray,
    *,
    seed: int = 42,
) -> dict[str, float]:
    """
    市場（オッズ・人気）特徴量をまとめてシャッフルした時の AUC 低下。

    「オッズを外したモデルを別途学習する」より安く、同じ問いに答えられる。
    低下が大きい = 市場の意見に強く依存している。
    """
    rng = np.random.default_rng(seed)
    present = [c for c in MARKET_FEATURES if c in X.columns]
    base = _auc(booster, X, y)
    if not present:
        return {"baseline_auc": base, "shuffled_auc": base, "auc_drop": 0.0}

    shuffled = X.copy()
    for col in present:
        # dtype を保つ位置シャッフル（permutation_auc_drop 内の注意書き参照）
        order = rng.permutation(len(shuffled))
        shuffled[col] = shuffled[col].iloc[order].set_axis(shuffled.index)
    shuffled_auc = _auc(booster, shuffled, y)
    return {
        "baseline_auc": base,
        "shuffled_auc": shuffled_auc,
        "auc_drop": base - shuffled_auc,
        "features": present,
    }


def run_sanity_checks(
    booster,
    X: pd.DataFrame,
    y: np.ndarray,
    *,
    seed: int = 42,
) -> dict:
    """評価時に呼ぶ入口。結果は metrics と一緒に artifact に残す。"""
    drops = permutation_auc_drop(booster, X, y, seed=seed)
    market = odds_dependency(booster, X, y, seed=seed)

    max_drop = max(drops.values()) if drops else 0.0
    threshold = max(DEAD_FEATURE_AUC_DROP, DEAD_FEATURE_RELATIVE * max_drop)
    dead = sorted(
        (f for f, d in drops.items() if d < threshold),
        key=lambda f: drops[f],
    )
    top = sorted(drops.items(), key=lambda kv: kv[1], reverse=True)[:10]

    result = {
        "permutation_auc_drop": drops,
        "top_features_by_auc_drop": top,
        "dead_features": dead,
        "dead_feature_threshold": threshold,
        "dead_feature_threshold_absolute": DEAD_FEATURE_AUC_DROP,
        "dead_feature_threshold_relative": DEAD_FEATURE_RELATIVE,
        "market_dependency": market,
    }

    logger.info(
        "サニティ: 市場特徴量をシャッフルすると AUC %.4f→%.4f (低下 %.4f)",
        market["baseline_auc"],
        market["shuffled_auc"],
        market["auc_drop"],
    )
    logger.info("サニティ: AUC 低下が大きい特徴量 上位5=%s", top[:5])
    if dead:
        logger.warning(
            "サニティ: シャッフルしても AUC が %.5f 以上落ちない特徴量が %d 個ある"
            "（実質機能していない可能性。壊れた集計・定数列を疑う）: %s",
            threshold,
            len(dead),
            dead,
        )
    return result
