"""
`app.ml.market_blend` のテスト。

🔴 **このモジュールの出力は「モデルは市場に情報を足せるか」の最終判定に使われる。**
α の標準誤差を過小に出すと「有意に足せている」と誤読し、金銭判断を誤る。
そこで **係数を既知の値に設定して合成データを作り、推定が真値を復元できるか**を
検査する（リカバリーテスト）。これが本体。
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.market_blend import (
    PROB_EPS,
    blend_probabilities,
    fit_binary_logistic,
    fit_conditional_logit,
    logit,
    race_log_loss,
    softmax_by_race,
)


def _simulate(
    n_races: int,
    alpha: float,
    beta: float,
    *,
    seed: int = 0,
    horses: int = 12,
    noise: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    真の係数 (alpha, beta) から勝ち馬を生成する。

    x1 = logit(p_model) 相当, x2 = logit(p_market) 相当。
    両者を相関させる（現実では市場とモデルは似た情報を持つ）。
    """
    rng = np.random.default_rng(seed)
    n = n_races * horses
    shared = rng.normal(0.0, 1.0, size=n)
    x1 = shared + rng.normal(0.0, noise, size=n)
    x2 = shared + rng.normal(0.0, noise, size=n)
    X = np.column_stack([x1, x2])
    race_ids = np.repeat(np.arange(n_races), horses)

    v = alpha * x1 + beta * x2
    p = softmax_by_race(v, race_ids.astype("int64"), n_races)
    y = np.zeros(n)
    for r in range(n_races):
        m = race_ids == r
        idx = np.flatnonzero(m)
        y[rng.choice(idx, p=p[m] / p[m].sum())] = 1.0
    return X, race_ids, y


class TestLogit:
    def test_symmetric_around_half(self):
        assert logit(np.array([0.5]))[0] == pytest.approx(0.0)
        assert logit(np.array([0.75]))[0] == pytest.approx(-logit(np.array([0.25]))[0])

    def test_extremes_are_clipped_not_infinite(self):
        out = logit(np.array([0.0, 1.0]))
        assert np.all(np.isfinite(out))
        assert out[0] == pytest.approx(np.log(PROB_EPS / (1 - PROB_EPS)))

    def test_monotonic(self):
        out = logit(np.array([0.01, 0.1, 0.5, 0.9]))
        assert np.all(np.diff(out) > 0)


class TestSoftmaxByRace:
    def test_sums_to_one_per_race(self):
        codes = np.array([0, 0, 0, 1, 1])
        p = softmax_by_race(np.array([1.0, 2.0, 3.0, 0.5, 0.5]), codes, 2)
        assert p[:3].sum() == pytest.approx(1.0)
        assert p[3:].sum() == pytest.approx(1.0)

    def test_equal_utilities_give_uniform(self):
        codes = np.zeros(4, dtype="int64")
        p = softmax_by_race(np.zeros(4), codes, 1)
        assert np.allclose(p, 0.25)

    def test_large_values_do_not_overflow(self):
        """レースごとに最大値を引いているので 1e4 でも inf/NaN にならない。"""
        codes = np.zeros(3, dtype="int64")
        p = softmax_by_race(np.array([1e4, 1e4 - 1, 1e4 - 2]), codes, 1)
        assert np.all(np.isfinite(p)) and p.sum() == pytest.approx(1.0)

    def test_adding_a_race_wide_constant_changes_nothing(self):
        """
        🔴 切片が識別できない理由そのもの。レース内で全馬に同じ値を足しても
        確率は変わらない（＝γ は尤度から消える）。
        """
        codes = np.array([0, 0, 1, 1])
        v = np.array([0.3, -0.7, 1.2, 0.4])
        base = softmax_by_race(v, codes, 2)
        shifted = softmax_by_race(v + np.array([5.0, 5.0, -3.0, -3.0]), codes, 2)
        assert np.allclose(base, shifted)


class TestCoefficientRecovery:
    """真の係数を復元できるか。ここが本体。"""

    @pytest.mark.parametrize(
        "alpha,beta",
        [(0.0, 1.0), (0.5, 1.0), (1.0, 1.0), (1.0, 0.0), (0.3, 1.5)],
    )
    def test_recovers_true_coefficients(self, alpha, beta):
        X, race_ids, y = _simulate(6_000, alpha, beta, seed=1)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])
        assert res["converged"]
        a = res["coefficients"]["alpha"]
        b = res["coefficients"]["beta"]
        # 95%CI が真値を含むこと（これが標準誤差の妥当性の検査でもある）
        assert a["ci95"][0] <= alpha <= a["ci95"][1], f"alpha CI={a['ci95']}"
        assert b["ci95"][0] <= beta <= b["ci95"][1], f"beta CI={b['ci95']}"

    def test_alpha_zero_is_not_flagged_significant(self):
        """
        🔴 最重要。真に α=0 のデータで「有意」と言ってはいけない。

        これが偽陽性を出すなら、「モデルは市場に情報を足せる」という
        誤った結論を金銭判断に渡すことになる。
        """
        X, race_ids, y = _simulate(8_000, 0.0, 1.0, seed=2)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])
        a = res["coefficients"]["alpha"]
        assert a["p_value"] > 0.05, f"α=0 なのに有意と判定された (p={a['p_value']})"
        assert a["significant_at_5pct"] is False

    def test_alpha_nonzero_is_detected(self):
        """逆向き: 真に α>0 なら検出できること（検出力の確認）。"""
        X, race_ids, y = _simulate(8_000, 0.6, 1.0, seed=3)
        a = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])[
            "coefficients"
        ]["alpha"]
        assert a["p_value"] < 0.01
        assert a["estimate"] > 0

    def test_false_positive_rate_is_near_nominal(self):
        """
        α=0 のデータを20回作って、5%水準の偽陽性がおよそ名目どおりか。

        標準誤差が過小なら偽陽性が跳ね上がる。20回中5回以上出たら異常。
        """
        hits = 0
        for s in range(20):
            X, race_ids, y = _simulate(1_500, 0.0, 1.0, seed=100 + s)
            a = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])[
                "coefficients"
            ]["alpha"]
            hits += int(a["p_value"] < 0.05)
        assert hits <= 4, f"20回中 {hits} 回の偽陽性（名目 5% なら期待 1 回）"

    def test_standard_error_shrinks_with_sqrt_n(self):
        se = {}
        for n in (1_000, 4_000):
            X, race_ids, y = _simulate(n, 0.5, 1.0, seed=4)
            se[n] = fit_conditional_logit(
                X, race_ids, y, feature_names=["alpha", "beta"]
            )["coefficients"]["alpha"]["std_error"]
        # 4倍のデータなら標準誤差はおよそ半分
        assert se[4_000] == pytest.approx(se[1_000] / 2.0, rel=0.35)


class TestStructuralGuards:
    def test_race_without_exactly_one_winner_raises(self):
        X = np.zeros((4, 2))
        race_ids = np.array([0, 0, 1, 1])
        with pytest.raises(ValueError, match="ちょうど1頭でない"):
            fit_conditional_logit(X, race_ids, np.array([1.0, 1.0, 1.0, 0.0]))

    def test_race_with_no_winner_raises(self):
        """未確定レースを黙って混ぜると尤度が壊れる。"""
        X = np.zeros((4, 2))
        with pytest.raises(ValueError, match="ちょうど1頭でない"):
            fit_conditional_logit(
                X, np.array([0, 0, 1, 1]), np.array([1.0, 0.0, 0.0, 0.0])
            )

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="長さ不一致"):
            fit_conditional_logit(
                np.zeros((4, 2)), np.array([0, 0, 1, 1]), np.array([1.0, 0.0])
            )

    def test_race_constant_feature_is_unidentified(self):
        """
        レース内で分散が無い列（切片など）は情報行列が特異になる。
        標準誤差が NaN か極端に大きくなり、**誤って有意にならない**こと。
        """
        n_races, horses = 500, 8
        rng = np.random.default_rng(5)
        x1 = rng.normal(size=n_races * horses)
        const = np.ones(n_races * horses)  # 切片相当
        race_ids = np.repeat(np.arange(n_races), horses)
        y = np.zeros(n_races * horses)
        for r in range(n_races):
            idx = np.flatnonzero(race_ids == r)
            y[rng.choice(idx)] = 1.0
        res = fit_conditional_logit(
            np.column_stack([x1, const]), race_ids, y, feature_names=["x1", "const"]
        )
        c = res["coefficients"]["const"]
        assert not np.isfinite(c["std_error"]) or c["std_error"] > 1e3
        assert c["significant_at_5pct"] is False


class TestRaceLogLoss:
    def test_perfect_prediction_gives_zero(self):
        p = np.array([1.0, 0.0, 1.0, 0.0])
        y = np.array([1.0, 0.0, 1.0, 0.0])
        assert race_log_loss(p, np.array([0, 0, 1, 1]), y) == pytest.approx(0.0)

    def test_uniform_prediction_equals_log_field_size(self):
        """8頭立てで一様なら -log(1/8) = log 8。"""
        codes = np.repeat([0, 1], 8)
        p = np.full(16, 1 / 8)
        y = np.zeros(16)
        y[0] = 1.0
        y[8] = 1.0
        assert race_log_loss(p, codes, y) == pytest.approx(np.log(8))

    def test_lower_is_better(self):
        codes = np.repeat([0], 4)
        y = np.array([1.0, 0.0, 0.0, 0.0])
        good = race_log_loss(np.array([0.7, 0.1, 0.1, 0.1]), codes, y)
        bad = race_log_loss(np.array([0.1, 0.3, 0.3, 0.3]), codes, y)
        assert good < bad

    def test_only_the_winner_contributes(self):
        """ハズレ馬の確率を動かしても（正規化を崩さない限り）値は同じ。"""
        codes = np.repeat([0], 4)
        y = np.array([1.0, 0.0, 0.0, 0.0])
        a = race_log_loss(np.array([0.4, 0.2, 0.2, 0.2]), codes, y)
        b = race_log_loss(np.array([0.4, 0.5, 0.05, 0.05]), codes, y)
        assert a == pytest.approx(b)


class TestBlendProbabilities:
    def test_sums_to_one_per_race(self):
        X, race_ids, _ = _simulate(50, 0.5, 1.0, seed=6)
        p = blend_probabilities(X, race_ids, [0.5, 1.0])
        s = pd.Series(p).groupby(race_ids).sum()
        assert np.allclose(s.to_numpy(), 1.0)

    def test_zero_alpha_ignores_the_model_column(self):
        """α=0 なら p_model 側をどう変えても結果が変わらないこと。"""
        X, race_ids, _ = _simulate(30, 0.5, 1.0, seed=7)
        base = blend_probabilities(X, race_ids, [0.0, 1.0])
        X2 = X.copy()
        X2[:, 0] = np.random.default_rng(8).normal(size=len(X2))
        assert np.allclose(base, blend_probabilities(X2, race_ids, [0.0, 1.0]))


class TestBinaryLogisticIsLabelledAsInferior:
    def test_returns_intercept_and_a_caveat(self):
        X, _, y = _simulate(500, 0.5, 1.0, seed=9)
        res = fit_binary_logistic(X, y)
        assert "intercept" in res
        assert "標準誤差が過小" in res["caveat"]
