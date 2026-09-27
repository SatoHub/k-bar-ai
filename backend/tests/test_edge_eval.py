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

    def test_empty_input_returns_none_not_crash(self):
        res = calibration(np.array([]), np.array([]))
        assert res["n"] == 0 and res["ece"] is None

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

    def test_roi_just_above_one_with_wide_ci_is_not_yes(self):
        """ROI が 1.00 をわずかに超えても CI がまたげば「見込みあり」と言わない。"""
        rng = np.random.default_rng(9)
        odds = rng.uniform(2.0, 4.0, size=3_000)
        won = (rng.uniform(size=3_000) < (1.02 / odds)).astype(float)
        r = roi_summary(pd.Series(odds), pd.Series(won), bootstrap_samples=3_000)
        if r["ci95"][0] <= 1.0:
            assert r["verdict"] != VERDICT_YES


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

    def test_empty_returns_nan(self):
        lo, hi = bootstrap_ci(np.array([]))
        assert np.isnan(lo) and np.isnan(hi)
