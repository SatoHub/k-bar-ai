"""
`app.ml.edge_eval` のテスト。

🔴 **このモジュールは金銭の判断に使われる。** 特に
「サンプルが少ないのに高ROIが出た時、ちゃんと判定不能を返すか」を重点的に検査する。
2026-09-27 に 113点で ROI 106.6% を見て一瞬「市場が勝っている」と読みかけた
（実際はノイズ）のが、このテスト群の存在理由である。
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.edge_eval import (
    BREAKEVEN_ROI,
    MIN_BETS,
    VERDICT_NO,
    VERDICT_UNDECIDABLE,
    VERDICT_YES,
    bootstrap_ci,
    calibration,
    market_implied_prob,
    normalize_within_race,
    required_bets,
    roi_summary,
)


class TestMarketImpliedProb:
    def test_normalized_sums_to_one_per_race(self):
        df = pd.DataFrame(
            {
                "race": ["A", "A", "A", "B", "B"],
                "odds": [2.0, 4.0, 8.0, 1.5, 3.0],
            }
        )
        p = market_implied_prob(df["odds"], df["race"], method="normalized")
        sums = p.groupby(df["race"]).sum()
        assert np.allclose(sums.to_numpy(), 1.0)

    def test_normalized_ranks_by_odds(self):
        """オッズが低い馬のほうが市場勝率は高い。"""
        df = pd.DataFrame({"race": ["A"] * 3, "odds": [2.0, 4.0, 8.0]})
        p = market_implied_prob(df["odds"], df["race"])
        assert p.iloc[0] > p.iloc[1] > p.iloc[2]

    def test_takeout_method_applies_measured_takeout(self):
        df = pd.DataFrame({"race": ["A"], "odds": [2.0]})
        p = market_implied_prob(df["odds"], df["race"], method="takeout")
        assert p.iloc[0] == pytest.approx(0.5 / 1.2529)

    def test_takeout_does_not_sum_to_one(self):
        """近似であることを明示的に固定する（normalized との差が意味を持つ）。"""
        df = pd.DataFrame({"race": ["A"] * 3, "odds": [2.0, 4.0, 8.0]})
        total = market_implied_prob(df["odds"], df["race"], method="takeout").sum()
        assert not np.isclose(total, 1.0)

    @pytest.mark.parametrize("bad", [0.0, -1.0, np.nan])
    def test_invalid_odds_become_nan_and_do_not_poison_race(self, bad):
        df = pd.DataFrame({"race": ["A"] * 3, "odds": [2.0, 4.0, bad]})
        p = market_implied_prob(df["odds"], df["race"])
        assert pd.isna(p.iloc[2])
        # 有効な2頭だけで正規化され、合計は1になる
        assert p.iloc[:2].sum() == pytest.approx(1.0)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            market_implied_prob(pd.Series([2.0]), pd.Series(["A"]), method="nope")


class TestNormalizeWithinRace:
    def test_sums_to_one(self):
        race = pd.Series(["A", "A", "B", "B", "B"])
        p = normalize_within_race(pd.Series([0.1, 0.3, 0.2, 0.2, 0.2]), race)
        assert np.allclose(p.groupby(race).sum().to_numpy(), 1.0)

    def test_removes_overall_level_shift(self):
        """モデルが全頭を2倍高く出しても正規化後は同じになる。"""
        race = pd.Series(["A"] * 3)
        base = normalize_within_race(pd.Series([0.1, 0.2, 0.3]), race)
        doubled = normalize_within_race(pd.Series([0.2, 0.4, 0.6]), race)
        assert np.allclose(base.to_numpy(), doubled.to_numpy())

    def test_all_zero_race_yields_nan_not_division_error(self):
        race = pd.Series(["A", "A"])
        p = normalize_within_race(pd.Series([0.0, 0.0]), race)
        assert p.isna().all()


class TestCalibration:
    def test_perfectly_calibrated_has_near_zero_ece(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0.02, 0.5, size=40_000)
        y = (rng.uniform(size=len(p)) < p).astype(float)
        res = calibration(p, y)
        assert res["ece"] < 0.01
        assert res["calibration_ok"] is True

    def test_systematically_overconfident_is_detected(self):
        """予測を一律 +0.15 ずらすと ECE がおよそ 0.15 になる。"""
        rng = np.random.default_rng(1)
        true_p = rng.uniform(0.05, 0.4, size=40_000)
        y = (rng.uniform(size=len(true_p)) < true_p).astype(float)
        res = calibration(np.clip(true_p + 0.15, 0, 1), y)
        assert res["ece"] == pytest.approx(0.15, abs=0.02)
        assert res["calibration_ok"] is False

    def test_bins_are_equal_frequency_not_equal_width(self):
        """0付近に密集した分布でも全ビンに件数が入ること。"""
        p = np.concatenate([np.linspace(0.001, 0.02, 9_000), [0.9] * 1_000])
        y = np.zeros_like(p)
        res = calibration(p, y, n_bins=10)
        counts = [b["count"] for b in res["bins"]]
        assert len(res["bins"]) >= 5
        # 等幅ビンなら1つのビンに9000件入ってしまう
        assert max(counts) < 5_000

    def test_gap_sign_shows_direction(self):
        p = np.full(1_000, 0.5)
        y = np.zeros(1_000)  # 実測0% なのに 50% と言っている
        res = calibration(p, y)
        assert res["bins"][0]["gap"] == pytest.approx(0.5)
        assert res["brier"] == pytest.approx(0.25)

    def test_ece_is_weighted_by_bin_count_not_a_plain_average(self):
        """
        🔴 ECE はビンごとの**件数で重み付け**する。単純平均にしてはいけない。

        件数が偏っている時、単純平均は「件数の少ないビンの大きなずれ」を
        過大評価し、キャリブレーションが実際より悪く見える（あるいはその逆）。
        等頻度ビンだと件数がほぼ揃うので、**同値を大量に混ぜて意図的に偏らせる**。
        これが無いと重み付けを外す実装変更を誰も検出できない
        （test-reviewer の mutation 7 が素通りした穴）。
        """
        rng = np.random.default_rng(21)
        spread = rng.uniform(0.0, 0.5, size=5_000)  # ばらけた側
        clumped = np.full(5_000, 0.9)  # 同値の塊 → 1ビンに集まる
        p = np.concatenate([spread, clumped])
        y = np.concatenate([np.zeros(5_000), np.ones(5_000)])

        res = calibration(p, y, n_bins=10)
        counts = np.array([b["count"] for b in res["bins"]], dtype="float64")
        gaps = np.array([abs(b["gap"]) for b in res["bins"]], dtype="float64")

        assert counts.max() / counts.min() > 3, (
            "前提: ビンの件数が偏っていること。偏っていないと"
            "重み付けの有無で差が出ず、検査にならない"
        )
        weighted = float((counts * gaps).sum() / counts.sum())
        plain = float(gaps.mean())
        assert abs(weighted - plain) > 0.02, (
            "前提: 重み付き平均と単純平均がはっきり違うデータであること"
        )
        assert res["ece"] == pytest.approx(weighted, abs=1e-9)
        assert res["ece"] != pytest.approx(plain, abs=0.01)

    def test_constant_prediction_model_is_not_calibration_ok(self):
        """
        🔴 定数を吐くモデルを「キャリブレーションOK」にしてはいけない。

        ビンが1つしか作れないと ECE は「全体平均の予測 vs 全体の実測率」に
        なり、ほぼ 0 になる。それを OK として EV 判定の前提を通すと
        **識別力ゼロのモデルが検証済みとして扱われる**
        （security-reviewer が実測で検出: ECE=0.0 / calibration_ok=True）。
        """
        n = 10_000
        p = np.full(n, 1 / 13)
        rng = np.random.default_rng(41)
        y = (rng.uniform(size=n) < 1 / 13).astype(float)
        res = calibration(p, y)
        assert res["n_bins_effective"] == 1
        assert res["ece"] < 0.02, "前提: ECE 自体は小さく出てしまうこと"
        assert res["degenerate"] is True
        assert res["calibration_ok"] is False

    def test_predictions_collapsed_into_few_bins_are_not_calibration_ok(self):
        """
        逆向きの誤差が打ち消し合って ECE が過小に出る経路を塞ぐ。

        予測の 90% が同値だと分位境界が潰れて1ビンになり、
        「3%しか勝たない群」と「90%勝つ群」が同じビンで相殺される
        （code-reviewer が実測: 報告 ECE 0.0104 / 本来 0.0466）。
        """
        p = np.concatenate([np.full(9_050, 0.05), np.full(950, 0.60)])
        y = np.concatenate(
            [
                (np.arange(9_050) % 100 < 3).astype(float),  # 約3%
                (np.arange(950) % 10 < 9).astype(float),  # 約90%
            ]
        )
        res = calibration(p, y, n_bins=10)
        assert res["n_bins_effective"] * 2 < 10, "前提: ビンが潰れること"
        assert res["degenerate"] is True
        assert res["calibration_ok"] is False

    def test_well_spread_predictions_are_not_flagged_degenerate(self):
        """正常なケースを degenerate と誤判定しない（偽陽性の確認）。"""
        rng = np.random.default_rng(42)
        p = rng.uniform(0.01, 0.4, size=20_000)
        y = (rng.uniform(size=20_000) < p).astype(float)
        res = calibration(p, y)
        assert res["n_bins_effective"] == 10
        assert res["degenerate"] is False
        assert res["calibration_ok"] is True

    def test_empty_input_returns_none_not_crash(self):
        res = calibration(np.array([]), np.array([]))
        assert res["n"] == 0 and res["ece"] is None
        assert res["calibration_ok"] is False

    def test_nan_rows_are_dropped(self):
        res = calibration(np.array([0.5, np.nan, 0.5]), np.array([1.0, 1.0, np.nan]))
        assert res["n"] == 1


class TestRoiMath:
    def test_roi_is_payout_over_stake(self):
        """3点賭けて1点的中(オッズ5.0) → 払戻5 / 賭け3 = 1.667。"""
        r = roi_summary(
            pd.Series([5.0, 3.0, 10.0]),
            pd.Series([1, 0, 0]),
            bootstrap_samples=200,
        )
        assert r["bets"] == 3
        assert r["roi"] == pytest.approx(5.0 / 3.0)
        assert r["hit_rate"] == pytest.approx(1 / 3)

    def test_all_losses_gives_zero_roi(self):
        r = roi_summary(
            pd.Series([2.0] * 10), pd.Series([0] * 10), bootstrap_samples=50
        )
        assert r["roi"] == 0.0

    def test_breakeven_is_one_not_takeout(self):
        """🔴 損益分岐は 1.00。0.80 を分岐点にすると赤字を黒字と読む。"""
        assert BREAKEVEN_ROI == 1.0
        r = roi_summary(
            pd.Series([2.0] * 1_000),
            pd.Series([1, 0] * 500),  # 的中50% → ROI=1.0
            bootstrap_samples=200,
        )
        assert r["roi"] == pytest.approx(1.0)
        assert r["is_profitable_point_estimate"] is False

    @pytest.mark.parametrize("bad_odds", [0.0, -3.0, np.nan])
    def test_invalid_odds_rows_are_excluded_from_denominator(self, bad_odds):
        r = roi_summary(
            pd.Series([2.0, 2.0, bad_odds]),
            pd.Series([1, 0, 0]),
            bootstrap_samples=50,
        )
        assert r["bets"] == 2
        assert r["roi"] == pytest.approx(1.0)

    def test_unsettled_rows_are_excluded(self):
        """着順未確定(NaN)をハズレとして数えると ROI が過小になる。"""
        r = roi_summary(
            pd.Series([2.0, 2.0, 2.0]),
            pd.Series([1.0, 0.0, np.nan]),
            bootstrap_samples=50,
        )
        assert r["bets"] == 2
        assert r["roi"] == pytest.approx(1.0)

    def test_empty_input_is_undecidable(self):
        r = roi_summary(pd.Series([], dtype=float), pd.Series([], dtype=float))
        assert r["bets"] == 0 and r["verdict"] == VERDICT_UNDECIDABLE

    def test_zero_bet_result_has_the_same_keys_as_a_normal_result(self):
        """
        🔴 0点でもキーの形を変えない。

        以前 `ci95` を落としていたため、呼び出し側が**全評価を終えた後に**
        TypeError で落ち、JSON も残らなかった（codex と security-reviewer が
        独立に指摘）。形が同じなら呼び出し側が壊れない。
        """
        empty = roi_summary(pd.Series([], dtype=float), pd.Series([], dtype=float))
        normal = roi_summary(
            pd.Series([2.0] * 10),
            pd.Series([1.0] * 5 + [0.0] * 5),
            bootstrap_samples=50,
        )
        assert set(empty) == set(normal)
        assert empty["ci95"] == (None, None)

    def test_length_mismatch_raises_instead_of_silently_returning_nan(self):
        """
        長さが違う入力は例外にする。黙って空になるのが最悪。

        pandas は index でアライメントするため、放置すると母集団が
        静かに 0 になる（code-reviewer が実測で指摘）。
        """
        with pytest.raises(ValueError, match="長さが一致しない"):
            roi_summary(pd.Series([2.0, 3.0]), pd.Series([1.0]))
        with pytest.raises(ValueError, match="長さが一致しない"):
            market_implied_prob(pd.Series([2.0, 3.0]), pd.Series(["A"]))

    def test_mismatched_index_does_not_produce_all_nan(self):
        """index がずれていても位置で対応させる（全 NaN にならない）。"""
        odds = pd.Series([2.0, 4.0], index=[100, 200])
        race = pd.Series(["A", "A"], index=[0, 1])
        p = market_implied_prob(odds, race)
        assert p.notna().all()
        assert p.sum() == pytest.approx(1.0)
        # 戻り値は呼び出し側の index を保つ（df への代入が壊れないため）
        assert list(p.index) == [100, 200]

    def test_required_bets_rule_is_equivalent_to_the_normal_approximation(self):
        """
        事前登録 §1-3 の「必要Nを逆算して満たさなければ点数不足」が、
        正規近似の半幅 0.10 と**厳密に同値**であることを固定する。

        `need = (Z95·sd/0.1)^2` なので `n >= need` ⟺ `Z95·sd/√n <= 0.1`。
        判定にこの条件を足したのは、bootstrap CI が退化して不当に狭くなった時に
        正規近似側で弾くため（code-reviewer M3）。

        ⚠️ **実測では、この条件だけが効くケースは見つからなかった。**
           「bootstrap 半幅 ≤ 0.10 なのに n < need」になる入力を
           オッズ帯・点数・的中率の 75 通りで探して 0 件
           （security-reviewer も 200 試行で 0 件）。
           したがってこれは**厳しい側への文書整合であって、
           挙動が変わることを実証できたわけではない**。
        """
        rng = np.random.default_rng(51)
        for n, hit in [(600, 0.05), (2_000, 0.2), (5_000, 0.1)]:
            odds = rng.uniform(1.5, 20.0, size=n)
            won = (rng.uniform(size=n) < hit).astype(float)
            r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=1_500)
            normal_half = 1.959964 * r["payoff_sd"] / np.sqrt(n)
            assert (r["bets"] >= r["required_bets_for_target"]) == (normal_half <= 0.10)

    def test_precise_but_clearly_losing_sample_is_verdict_no_not_undecidable(self):
        """
        当たりが極端に少なくても、ROI が精度よく 0 付近と分かるなら
        「有意に赤字」と断言してよい（判定不能に逃げない）。

        600点で1的中・オッズ3.0 なら ROI 0.5%。bootstrap も正規近似も
        半幅 0.01 未満で一致する（実測）。統計的に妥当な断定。
        """
        r = roi_summary(
            pd.Series([3.0] * 600),
            pd.Series([1.0] + [0.0] * 599),
            bootstrap_samples=3_000,
        )
        assert r["bets"] >= MIN_BETS
        assert r["ci_halfwidth"] < 0.05
        assert r["bets"] >= r["required_bets_for_target"]
        assert r["verdict"] == VERDICT_NO

    def test_index_misalignment_does_not_shuffle_pairs(self):
        """odds と winner の index がずれていても行の対応が壊れないこと。"""
        odds = pd.Series([5.0, 2.0], index=[10, 11])
        won = pd.Series([1.0, 0.0], index=[0, 1])
        r = roi_summary(odds, won, bootstrap_samples=50)
        assert r["roi"] == pytest.approx(5.0 / 2)


class TestVerdictGuardsAgainstSmallSamples:
    """🔴 ここが本体。少数サンプルの高ROIを「見込みあり」にしてはいけない。"""

    def test_small_sample_with_huge_roi_is_undecidable(self):
        """113点で ROI 130% — 実際に起きた罠。判定不能でなければならない。"""
        rng = np.random.default_rng(7)
        odds = rng.uniform(5, 30, size=113)
        won = np.zeros(113)
        won[:12] = 1.0
        r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=2_000)
        assert r["bets"] < MIN_BETS
        assert r["verdict"] == VERDICT_UNDECIDABLE
        assert "点数不足" in r["verdict_reason"]

    def test_enough_bets_but_wide_ci_is_undecidable(self):
        """点数は足りても人気薄ばかりだと CI が広く判定できない。"""
        rng = np.random.default_rng(8)
        odds = rng.uniform(40, 120, size=1_000)
        won = (rng.uniform(size=1_000) < 0.015).astype(float)
        r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=2_000)
        assert r["bets"] >= MIN_BETS
        assert r["ci_halfwidth"] > 0.10
        assert r["verdict"] == VERDICT_UNDECIDABLE
        assert "精度不足" in r["verdict_reason"]

    def test_clearly_losing_large_sample_is_verdict_no(self):
        odds = pd.Series([2.0] * 20_000)
        won = pd.Series(([1.0] + [0.0] * 3) * 5_000)  # 的中25% → ROI 0.5
        r = roi_summary(odds, won, bootstrap_samples=1_000)
        assert r["roi"] == pytest.approx(0.5)
        assert r["verdict"] == VERDICT_NO

    def test_clearly_winning_large_sample_is_verdict_yes(self):
        odds = pd.Series([2.0] * 20_000)
        won = pd.Series(([1.0, 1.0, 1.0] + [0.0]) * 5_000)  # 的中75% → ROI 1.5
        r = roi_summary(odds, won, bootstrap_samples=1_000)
        assert r["roi"] == pytest.approx(1.5)
        assert r["verdict"] == VERDICT_YES

    def test_roi_above_one_but_ci_straddles_breakeven_is_not_yes(self):
        """
        ROI が 1.00 を超えていても CI が 1.00 をまたげば「見込みあり」と言わない。

        ⚠️ 以前この検査は `if r["ci95"][0] <= 1.0:` の中に assert を置いていたため、
           **その条件が一度も成立せず完全な無検査だった**（test-reviewer が
           mutation testing で検出。実測で ci_lo=1.0153 だった）。
           条件分岐を使わず、CI が確実にまたぐデータで無条件に検査する。
        """
        rng = np.random.default_rng(11)
        n = 6_000
        # 低オッズ帯なら精度要件（CI半幅≤0.10）は満たせる。真の ROI を
        # ちょうど 1.00 に置くことで CI が損益分岐をまたぐ状況を作る。
        odds = rng.uniform(1.3, 2.0, size=n)
        won = (rng.uniform(size=n) < (1.0 / odds)).astype(float)
        r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=3_000)

        assert r["ci_halfwidth"] <= 0.10, "前提: 精度要件は満たしていること"
        assert r["ci95"][0] < 1.0 < r["ci95"][1], "前提: CI が 1.00 をまたぐこと"
        assert r["verdict"] == VERDICT_UNDECIDABLE
        assert "またぐ" in r["verdict_reason"]

    def test_precision_is_checked_before_profitability(self):
        """
        🔴 判定の**順序**を固定する。点数不足の判定は「儲かってそうか」より先。

        これが無いと「精度チェックより先に CI 下限を見る」実装に変えても
        どのテストも落ちない（test-reviewer の mutation 3 が素通りした穴）。
        少数サンプルで偶然 CI 下限が 1.00 を超えるケースを意図的に作る。
        """
        # 50点・オッズ3.0・40勝 → ROI 2.4。CI 下限は 1.00 をはるかに超える。
        odds = pd.Series([3.0] * 50)
        won = pd.Series([1.0] * 40 + [0.0] * 10)
        r = roi_summary(odds, won, bootstrap_samples=3_000)

        assert r["bets"] < MIN_BETS, "前提: 点数が下限未満であること"
        assert r["ci95"][0] > BREAKEVEN_ROI, (
            "前提: CI 下限が損益分岐を超えていること"
            "（超えていないと順序の検査にならない）"
        )
        assert r["verdict"] == VERDICT_UNDECIDABLE
        assert "点数不足" in r["verdict_reason"]

    def test_wide_ci_beats_profitability_even_when_bets_are_enough(self):
        """
        点数が下限を満たしていても、精度不足なら「見込みあり」より優先される。

        上のテストは `n < MIN_BETS` の枝を守る。こちらは CI 半幅の枝を守る。
        """
        rng = np.random.default_rng(12)
        n = 1_000
        odds = rng.uniform(50, 120, size=n)
        # 儲かるように当選を多めに作る（ROI は 1.00 を大きく超える）
        won = (rng.uniform(size=n) < 0.05).astype(float)
        r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=3_000)

        assert r["bets"] >= MIN_BETS, "前提: 点数は下限を満たすこと"
        assert r["ci95"][0] > BREAKEVEN_ROI, "前提: CI 下限が損益分岐を超えること"
        assert r["ci_halfwidth"] > 0.10, "前提: 精度要件を満たさないこと"
        assert r["verdict"] == VERDICT_UNDECIDABLE
        assert "精度不足" in r["verdict_reason"]


class TestSampleSizeArithmetic:
    def test_required_bets_matches_precommitted_doc_values(self):
        """docs/20260927-oddsfree-edge-criteria.md の表と一致すること。"""
        assert required_bets(1.078) == pytest.approx(446, abs=2)
        assert required_bets(8.659) == pytest.approx(28_803, abs=50)

    def test_required_bets_grows_with_square_of_sd(self):
        assert required_bets(2.0) == pytest.approx(4 * required_bets(1.0))

    def test_required_bets_nan_is_propagated(self):
        assert np.isnan(required_bets(float("nan")))


class TestBootstrap:
    def test_ci_brackets_the_sample_mean(self):
        rng = np.random.default_rng(3)
        payoffs = np.where(rng.uniform(size=5_000) < 0.2, 4.0, 0.0)
        lo, hi = bootstrap_ci(payoffs, samples=2_000)
        assert lo < payoffs.mean() < hi

    def test_ci_narrows_as_n_grows(self):
        rng = np.random.default_rng(4)

        def half(n):
            p = np.where(rng.uniform(size=n) < 0.2, 4.0, 0.0)
            lo, hi = bootstrap_ci(p, samples=1_500)
            return hi - lo

        assert half(20_000) < half(1_000)

    def test_deterministic_for_fixed_seed(self):
        p = np.array([0.0, 4.0] * 500)
        assert bootstrap_ci(p, samples=500, seed=1) == bootstrap_ci(
            p, samples=500, seed=1
        )

    def test_chunking_does_not_change_result(self):
        """チャンク境界で乱数列の消費がずれないこと。"""
        p = np.array([0.0, 4.0] * 500)
        one_shot = bootstrap_ci(p, samples=600, seed=1, chunk=600)
        chunked = bootstrap_ci(p, samples=600, seed=1, chunk=7)
        assert one_shot == pytest.approx(chunked, abs=0.05)

    def test_confidence_level_is_95_percent_not_something_narrower(self):
        """
        🔴 CI の**信頼水準そのもの**を固定する。

        「n が増えると狭くなる」「平均を挟む」だけでは、percentile を
        0.25/0.75 に変えられても検出できない（test-reviewer が、既存の検出は
        境界値の偶然によるものだと指摘）。大標本では bootstrap CI の半幅は
        正規近似 `1.96 × sd / √n` に近づくので、それと突き合わせる。
        """
        rng = np.random.default_rng(31)
        n = 30_000
        payoffs = np.where(rng.uniform(size=n) < 0.25, 4.0, 0.0)
        lo, hi = bootstrap_ci(payoffs, samples=4_000, seed=5)
        half = (hi - lo) / 2.0
        theory = 1.959964 * payoffs.std(ddof=1) / np.sqrt(n)
        # 50%区間なら理論値の約34%になるため、この許容では通らない
        assert half == pytest.approx(theory, rel=0.10)

    def test_empty_returns_nan(self):
        lo, hi = bootstrap_ci(np.array([]))
        assert np.isnan(lo) and np.isnan(hi)
