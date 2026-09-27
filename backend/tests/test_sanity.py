"""app.ml.sanity のテスト（DB 不要）。

サニティチェック自体が壊れていると「壊れた特徴量を見逃す」ので、
「役に立たない特徴量を本当に検出できるか」を合成データで確認する。
"""

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.ml.sanity import (
    DEAD_FEATURE_AUC_DROP,
    odds_dependency,
    permutation_auc_drop,
    run_sanity_checks,
)


def _fit_toy_model(n: int = 4000, seed: int = 0):
    """
    目的変数を決めるのは `signal` と `win_odds` だけ。
    `noise` と `constant` は無関係＝「実質機能していない特徴量」の正解。
    """
    rng = np.random.default_rng(seed)
    signal = rng.normal(size=n)
    win_odds = rng.uniform(1.5, 50.0, size=n)
    logit = 1.8 * signal - 0.08 * win_odds
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)

    X = pd.DataFrame(
        {
            "signal": signal,
            "win_odds": win_odds,
            "win_favorite": np.argsort(np.argsort(win_odds)) % 18 + 1,
            "noise": rng.normal(size=n),
            "constant": np.ones(n),
        }
    )
    booster = lgb.train(
        {"objective": "binary", "verbose": -1, "seed": seed, "num_leaves": 15},
        lgb.Dataset(X, label=y),
        num_boost_round=60,
    )
    return booster, X, y


class TestPermutationAucDrop:
    def test_useless_features_show_no_drop(self) -> None:
        """
        情報を持たない特徴量は、シャッフルしても AUC が落ちないこと。

        ⚠️ `noise` については「絶対に落ちない」とは言えない。
        小さい合成データだと LightGBM がノイズ列に過適合し、実測で
        0.02 程度 AUC が動いた。そのため絶対値ではなく
        「本物の signal に比べて桁違いに小さい」ことを検証する。
        この事実があるため、sanity 側の判定も相対基準を併用している。
        """
        booster, X, y = _fit_toy_model()
        drops = permutation_auc_drop(booster, X, y)

        # 定数列は情報がゼロなので、シャッフルしても何も変わらない
        assert drops["constant"] < DEAD_FEATURE_AUC_DROP, (
            f"定数列が重要と判定されている: {drops['constant']}"
        )
        # ノイズは signal より桁違いに小さいこと
        assert drops["noise"] < drops["signal"] / 5, (
            f"noise({drops['noise']}) が signal({drops['signal']}) に対して大きすぎる"
        )

    def test_real_signal_shows_drop(self) -> None:
        """本当に効いている特徴量は、シャッフルすると AUC が落ちること。"""
        booster, X, y = _fit_toy_model()
        drops = permutation_auc_drop(booster, X, y)

        assert drops["signal"] > DEAD_FEATURE_AUC_DROP * 10, (
            f"効いているはずの signal で AUC が落ちない: {drops['signal']}"
        )


class TestOddsDependency:
    def test_detects_market_dependency(self) -> None:
        """市場特徴量をシャッフルすると AUC が下がること（依存度が測れている）。"""
        booster, X, y = _fit_toy_model()
        result = odds_dependency(booster, X, y)

        assert result["auc_drop"] > 0, "市場特徴量への依存が検出できていない"
        assert result["shuffled_auc"] < result["baseline_auc"]
        assert set(result["features"]) == {"win_odds", "win_favorite"}


class TestRunSanityChecks:
    def test_dead_features_are_reported(self) -> None:
        """入口関数が「実質機能していない特徴量」を列挙すること。"""
        booster, X, y = _fit_toy_model()
        result = run_sanity_checks(booster, X, y)

        # 情報ゼロの定数列は必ず検出されること（今回のバグで壊れた集計も
        # ほぼ定数になっていたので、これが検知できれば同種の事故を拾える）
        assert "constant" in result["dead_features"]
        assert "signal" not in result["dead_features"]
        assert "win_odds" not in result["dead_features"]
        # 上位は AUC 低下の降順
        top = [f for f, _ in result["top_features_by_auc_drop"]]
        assert top[0] == "signal", f"最重要が signal でない: {top}"


class TestCategoricalFeatures:
    """
    categorical 列があってもサニティチェックが動くこと。

    ⚠️ 回帰テスト。当初 `rng.permutation(series.to_numpy())` で代入していたため
    categorical の dtype が落ち、LightGBM が
    "train and valid dataset categorical_feature do not match" で例外を投げた。
    本番の特徴量は surface / track_condition など6列が categorical なので、
    これを踏むと **学習が保存まで到達できず完全に止まる**（codex レビューで検出）。
    """

    def _fit_with_categorical(self, n: int = 800, seed: int = 0):
        rng = np.random.default_rng(seed)
        surface = pd.Categorical(rng.choice(["芝", "ダ"], n))
        num = rng.normal(size=n)
        y = (rng.uniform(size=n) < 1 / (1 + np.exp(-1.5 * num))).astype(int)
        X = pd.DataFrame({"num": num, "surface": surface})
        booster = lgb.train(
            {"objective": "binary", "verbose": -1, "seed": seed},
            lgb.Dataset(X, label=y, categorical_feature=["surface"]),
            num_boost_round=30,
        )
        return booster, X, y

    def test_permutation_works_with_categorical(self) -> None:
        booster, X, y = self._fit_with_categorical()
        drops = permutation_auc_drop(booster, X, y)
        assert set(drops) == {"num", "surface"}

    def test_dtype_is_preserved(self) -> None:
        """シャッフル後も categorical dtype が保たれること。"""
        booster, X, y = self._fit_with_categorical()
        before = X["surface"].dtype
        permutation_auc_drop(booster, X, y)
        assert X["surface"].dtype == before, "入力側の dtype が壊れている"

    def test_run_sanity_checks_with_categorical(self) -> None:
        booster, X, y = self._fit_with_categorical()
        result = run_sanity_checks(booster, X, y)
        assert "permutation_auc_drop" in result
