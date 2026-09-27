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
from scipy import stats

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


def _naive_log_likelihood(theta, X, race_ids, y) -> float:
    """
    **独立した素朴な実装**による条件付きロジットの対数尤度。

    被テスト実装（`bincount` と `np.maximum.at` を使ったベクトル化）とは
    別の経路（レースごとの素直なループ）で計算する。標準誤差の検証に使う
    参照実装なので、速さより読んで正しさが分かることを優先する。
    """
    theta = np.asarray(theta, dtype="float64")
    total = 0.0
    for r in np.unique(race_ids):
        m = np.asarray(race_ids) == r
        v = X[m] @ theta
        total += float(v[y[m] == 1.0][0] - np.log(np.sum(np.exp(v))))
    return total


class TestStandardErrorAgainstIndependentHessian:
    """
    🔴 標準誤差を**独立な経路**で検算する。

    情報行列 `I = Σ_r Cov_p(x)` の実装ミス（共分散の第2項を落とす、
    fitted な p ではなく一様確率を使う等）は、シミュレーションの
    CI 包含チェックでは弱い偶然頼みの検出しかできなかった
    （test-reviewer が mutation testing で実証）。
    素朴な対数尤度の**数値ヘッセ行列**と突き合わせれば決定論的に捕まる。
    """

    @staticmethod
    def _numeric_se(theta, X, race_ids, y, h: float = 1e-4) -> np.ndarray:
        k = len(theta)
        H = np.zeros((k, k))
        for i in range(k):
            for j in range(k):
                tpp, tpm, tmp, tmm = (
                    np.array(theta, dtype="float64") for _ in range(4)
                )
                tpp[i] += h
                tpp[j] += h
                tpm[i] += h
                tpm[j] -= h
                tmp[i] -= h
                tmp[j] += h
                tmm[i] -= h
                tmm[j] -= h
                H[i, j] = (
                    _naive_log_likelihood(tpp, X, race_ids, y)
                    - _naive_log_likelihood(tpm, X, race_ids, y)
                    - _naive_log_likelihood(tmp, X, race_ids, y)
                    + _naive_log_likelihood(tmm, X, race_ids, y)
                ) / (4 * h * h)
        return np.sqrt(np.diag(np.linalg.inv(-H)))

    @pytest.mark.parametrize("alpha,beta", [(0.4, 1.0), (1.2, 0.3)])
    def test_reported_se_matches_numeric_hessian(self, alpha, beta):
        X, race_ids, y = _simulate(1_200, alpha, beta, seed=77)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["a", "b"])
        reported = np.array([res["coefficients"][n]["std_error"] for n in ("a", "b")])
        numeric = self._numeric_se(res["theta"], X, np.asarray(race_ids), y)
        assert np.allclose(reported, numeric, rtol=0.02), (
            f"報告 SE={reported} vs 数値ヘッセ SE={numeric}"
        )

    def test_closed_form_minimal_case(self):
        """
        手計算できる最小構成で情報行列の値そのものを固定する。

        2レース×2頭、説明変数1つ。race0: x=[1,0] で1頭目が勝ち、
        race1: x=[0,1] で1頭目が勝ち。θ=0 での勾配は
        (1−0.5)+(0−0.5)=0 なので **MLE はちょうど θ=0**。
        そこでの情報量は Σ_r Cov_p(x) = (1−0)²/4 + (0−1)²/4 = 0.5。
        よって SE = 1/√0.5 = 1.41421。
        """
        X = np.array([[1.0], [0.0], [0.0], [1.0]])
        race_ids = np.array([0, 0, 1, 1])
        y = np.array([1.0, 0.0, 1.0, 0.0])
        res = fit_conditional_logit(X, race_ids, y, feature_names=["x"])
        c = res["coefficients"]["x"]
        assert c["estimate"] == pytest.approx(0.0, abs=1e-6)
        assert c["std_error"] == pytest.approx(np.sqrt(2.0), rel=1e-4)


class TestPValueFormula:
    """
    🔴 p 値が**両側**であることを決定論的に固定する。

    片側化（`2*sf` → `sf`）は実効的な有意水準を2倍（10%）にする＝
    ユーザーが最も懸念する「SE 過小で有意に見える」と同じ症状だが、
    シミュレーションベースのテストは27件すべて素通りした
    （test-reviewer が mutation testing で実証）。
    数式そのものを突き合わせれば偶然に依らず捕まる。
    """

    @pytest.mark.parametrize("alpha,beta,seed", [(0.0, 1.0, 5), (0.3, 1.0, 6)])
    def test_p_value_is_two_sided_normal_tail(self, alpha, beta, seed):
        X, race_ids, y = _simulate(800, alpha, beta, seed=seed)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["a", "b"])
        for c in res["coefficients"].values():
            expected = 2.0 * stats.norm.sf(abs(c["z"]))
            # ⚠️ `abs=0` が必須。pytest.approx の既定の絶対許容 1e-12 のままだと
            #    p≈1e-133 のような小さい値では**半分にしても一致扱いになり、
            #    この検査が無検査になる**（自分のテストで踏んだ）。
            assert c["p_value"] == pytest.approx(expected, rel=1e-9, abs=0.0)
            # 片側なら半分になるので、その値とは一致しないこと
            assert c["p_value"] != pytest.approx(expected / 2.0, rel=1e-6, abs=0.0)

    def test_z_is_estimate_over_standard_error(self):
        X, race_ids, y = _simulate(800, 0.5, 1.0, seed=7)
        for c in fit_conditional_logit(X, race_ids, y)["coefficients"].values():
            assert c["z"] == pytest.approx(c["estimate"] / c["std_error"], rel=1e-9)

    def test_ci_is_estimate_plus_minus_1_96_se(self):
        X, race_ids, y = _simulate(800, 0.5, 1.0, seed=8)
        for c in fit_conditional_logit(X, race_ids, y)["coefficients"].values():
            lo, hi = c["ci95"]
            assert lo == pytest.approx(c["estimate"] - 1.959964 * c["std_error"])
            assert hi == pytest.approx(c["estimate"] + 1.959964 * c["std_error"])


class TestCoefficientRecovery:
    """真の係数を復元できるか。ここが本体。"""

    @pytest.mark.parametrize(
        "alpha,beta",
        [(0.0, 1.0), (0.5, 1.0), (1.0, 1.0), (1.0, 0.0), (0.3, 1.5)],
    )
    def test_recovers_true_coefficients(self, alpha, beta):
        """
        推定値が真値から **3·SE 以内**にあること。

        ⚠️ 当初は 95%CI が真値を含むことを検査していたが、
           5組×2係数=10個の独立な95%CIを1回のシミュレーションで見るため
           **実装が正しくても約40%の確率でどれかが外れる**。
           実際 seed=31, 41 で落ちることを test-reviewer が実測した
           ＝seed 依存の flaky test だった。3·SE（片側あたり約0.13%）なら
           10個でも偶発失敗は 1% 未満に収まり、かつ SE の妥当性も検査できる。
        """
        X, race_ids, y = _simulate(6_000, alpha, beta, seed=1)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])
        assert res["converged"]
        for name, truth in (("alpha", alpha), ("beta", beta)):
            c = res["coefficients"][name]
            dev = abs(c["estimate"] - truth) / c["std_error"]
            assert dev < 3.0, (
                f"{name}: 推定 {c['estimate']:.4f} が真値 {truth} から "
                f"{dev:.2f}·SE 離れている"
            )

    @pytest.mark.parametrize("seed", [1, 31, 41])
    def test_recovery_is_not_seed_dependent(self, seed):
        """test-reviewer が落ちることを実測した seed でも通ること。"""
        X, race_ids, y = _simulate(6_000, 1.0, 0.0, seed=seed)
        res = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])
        for name, truth in (("alpha", 1.0), ("beta", 0.0)):
            c = res["coefficients"][name]
            assert abs(c["estimate"] - truth) / c["std_error"] < 3.0

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

    def test_z_statistic_follows_standard_normal_under_the_null(self):
        """
        🔴 α=0 のもとで z 統計量が N(0,1) に従うことを直接検定する。

        ⚠️ 当初は「20回中4回以下の偽陽性」で見ていたが、test-reviewer が
           二項分布で検出力を計算したところ **真の偽陽性率が2倍(10%)に
           悪化しても検出確率は 4.3%**、3倍でも17%しかなかった。
           つまり「SE が2〜3倍過小」というまさに最悪のケースを
           ほぼ素通りさせる設計だった。

        z の分布そのものを見れば、SE のスケール誤差は幅の違いとして
        直接現れる（SE が半分なら z は2倍に広がる）。
        Kolmogorov-Smirnov 検定は分布全体を使うので、
        裾の数え上げより検出力が高い。
        """
        zs = []
        for s in range(120):
            X, race_ids, y = _simulate(600, 0.0, 1.0, seed=1000 + s, horses=10)
            zs.append(
                fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])[
                    "coefficients"
                ]["alpha"]["z"]
            )
        zs = np.asarray(zs)
        ks_p = float(stats.kstest(zs, "norm").pvalue)
        assert ks_p > 0.01, (
            f"z が N(0,1) から外れている (KS p={ks_p:.4g}, "
            f"標本SD={zs.std(ddof=1):.3f}, 平均={zs.mean():.3f})。"
            "標準誤差のスケールを疑う"
        )
        # 分布の幅が 1 から大きく外れていないこと（SE のスケール誤差の直接検査）
        assert zs.std(ddof=1) == pytest.approx(1.0, abs=0.22), (
            f"z の標準偏差 {zs.std(ddof=1):.3f} が 1 から離れすぎている"
        )

    def test_false_positive_rate_is_near_nominal(self):
        """
        補助的な検査: 上の KS 検定と同じ標本で 5%水準の偽陽性率を見る。

        単独では検出力が低い（上の docstring 参照）ので、
        **KS 検定の補足としてのみ**置いておく。閾値は二項分布から導く:
        n=120, p=0.05 なら期待 6 件、上側99%点は 13 件。
        """
        hits = 0
        for s in range(120):
            X, race_ids, y = _simulate(600, 0.0, 1.0, seed=1000 + s, horses=10)
            a = fit_conditional_logit(X, race_ids, y, feature_names=["alpha", "beta"])[
                "coefficients"
            ]["alpha"]
            hits += int(a["p_value"] < 0.05)
        upper = int(stats.binom.ppf(0.99, 120, 0.05))
        assert hits <= upper, (
            f"120回中 {hits} 回の偽陽性（名目5%なら期待6件、上側99%点は {upper} 件）"
        )

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
