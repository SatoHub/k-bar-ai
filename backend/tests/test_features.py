"""Tests for feature engineering — especially future data leakage prevention."""

import numpy as np
import pytest
import pandas as pd

from app.ml.features import (
    _compute_horse_condition_features,
    _compute_horse_rolling_stats,
    _compute_jockey_stats,
    _compute_trainer_stats,
    build_feature_matrix,
)


def _make_sample_df(n_horses: int = 2, races_per_horse: int = 6) -> pd.DataFrame:
    """Create a minimal DataFrame mimicking the raw data structure."""
    rows = []
    for h in range(n_horses):
        for r in range(races_per_horse):
            rows.append(
                {
                    "entry_id": f"entry_{h}_{r}",
                    "race_id_str": f"race_{r}",
                    "race_date": pd.Timestamp(f"2020-01-{r + 1:02d}"),
                    "racecourse_name": "東京",
                    "surface": "芝",
                    "distance_m": 1600,
                    "track_condition": "良",
                    "weather": "晴",
                    "direction": "左",
                    "bracket_number": h + 1,
                    "post_position": h + 1,
                    "horse_age": 3,
                    "weight_carried_kg": 55.0,
                    "finish_position": (r % 5) + 1,  # 1,2,3,4,5,1,...
                    "last_3f_time": 34.0 + r * 0.1,
                    "win_odds": 5.0 + r,
                    "win_favorite": r + 1,
                    "horse_weight_kg": 480,
                    "horse_weight_diff": -2,
                    "prize_money_10k_yen": 100.0 * (6 - r),
                    "horse_uuid": f"horse_{h}",
                    "horse_name": f"Horse{h}",
                    "horse_sex": "牡",
                    "jockey_uuid": f"jockey_{h}",
                    "jockey_name": f"Jockey{h}",
                    "trainer_uuid": f"trainer_{h}",
                    "trainer_name": f"Trainer{h}",
                    "race_uuid": f"race_uuid_{r}",
                }
            )
    df = pd.DataFrame(rows)
    df["race_date"] = pd.to_datetime(df["race_date"])
    for col in [
        "distance_m",
        "bracket_number",
        "post_position",
        "horse_age",
        "horse_weight_kg",
        "horse_weight_diff",
        "win_favorite",
        "finish_position",
    ]:
        df[col] = df[col].astype("Int64")
    return df


class TestHorseRollingStats:
    """Verify that horse rolling stats use shift(1) to prevent leakage."""

    def test_first_race_has_nan(self):
        """Horse's first race should have NaN rolling stats (no prior data)."""
        df = _make_sample_df(n_horses=1, races_per_horse=5)
        result = _compute_horse_rolling_stats(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert pd.isna(first_row["horse_avg_finish_3"]), (
            "First race should have NaN for rolling avg (no prior data)"
        )

    def test_no_current_race_in_rolling(self):
        """Rolling stats for race N should NOT include race N's result."""
        df = _make_sample_df(n_horses=1, races_per_horse=6)
        result = _compute_horse_rolling_stats(df)

        horse_rows = result[result["horse_uuid"] == "horse_0"].reset_index(drop=True)

        # Row index 3 (4th race): rolling-3 should use races 1,2,3 (indices 0,1,2)
        # finish_position pattern: 1,2,3,4,5,1,...  so races 0,1,2 = [1,2,3]
        row3 = horse_rows.iloc[3]
        expected_avg = np.mean([1, 2, 3])  # indices 0,1,2
        assert abs(row3["horse_avg_finish_3"] - expected_avg) < 0.01, (
            f"Expected avg={expected_avg}, got {row3['horse_avg_finish_3']}"
        )

    def test_rolling_window_respects_size(self):
        """Rolling-5 with only 3 prior races should still work (min_periods=1)."""
        df = _make_sample_df(n_horses=1, races_per_horse=5)
        result = _compute_horse_rolling_stats(df)

        horse_rows = result[result["horse_uuid"] == "horse_0"].reset_index(drop=True)

        # Row 3 has 3 prior races, rolling-5 with min_periods=1 should use all 3
        row3 = horse_rows.iloc[3]
        assert not pd.isna(row3["horse_avg_finish_5"]), (
            "Rolling-5 should work with fewer than 5 prior races"
        )


class TestJockeyStats:
    """Verify jockey cumulative stats use shift(1)."""

    def test_first_ride_has_nan(self):
        """Jockey's first ride should have NaN cumulative stats."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_jockey_stats(df)

        first_row = result.iloc[0]
        assert pd.isna(first_row["jockey_win_rate"]), (
            "Jockey's first ride should have NaN win rate"
        )


class TestTrainerStats:
    """Verify trainer cumulative stats use shift(1)."""

    def test_first_entry_has_nan(self):
        """Trainer's first entry should have NaN cumulative stats."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_trainer_stats(df)

        first_row = result.iloc[0]
        assert pd.isna(first_row["trainer_win_rate"]), (
            "Trainer's first entry should have NaN win rate"
        )


class TestHorseCondition:
    """Verify horse condition features."""

    def test_first_race_no_days_since(self):
        """First race should have NaN days_since_last_race."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_horse_condition_features(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert pd.isna(first_row["days_since_last_race"]), (
            "First race should have NaN days_since_last_race"
        )

    def test_race_count_starts_at_zero(self):
        """race_count for the first entry should be 0 (no prior races)."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_horse_condition_features(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert first_row["race_count"] == 0, "First race should have race_count=0"


class TestBuildFeatureMatrix:
    """Test the full pipeline with a sample DataFrame."""

    def test_build_from_provided_df(self):
        """build_feature_matrix should work with a provided DataFrame."""
        df = _make_sample_df(n_horses=2, races_per_horse=6)
        result = build_feature_matrix(df)

        assert len(result) == 12  # 2 horses * 6 races
        assert "is_place" in result.columns
        assert "horse_avg_finish_3" in result.columns
        assert "jockey_win_rate" in result.columns
        assert "trainer_win_rate" in result.columns
        assert "days_since_last_race" in result.columns


# ===========================================================================
# グループ境界のリーク検査（2026-09-27 追加）
#
# ⚠️ なぜ既存のテストでは検出できなかったか:
#   上のテストは全て n_horses=1 / 単一の騎手・調教師で書かれている。
#   バグは「別のエンティティのデータを拾う」ものなので、
#   **エンティティが1つしか無いテストでは構造的に検出できない**。
#   「関数が呼べること」の検証と「境界で正しく切れていること」の検証は別物。
#
# 実際のバグ: features.py は shift(1) を groupby 内で正しく行っているが、
#   その後の rolling / expanding を **groupby の外** で呼んでいた。
#     grouped[col].shift(1).rolling(3).mean()   # ← 全体に対する rolling
#   このため各グループ先頭行が直前のグループの値を拾っていた。
# ===========================================================================


def _make_multi_entity_df() -> pd.DataFrame:
    """
    境界を踏むための合成データ。

    - horse_0 / jockey_0 / trainer_0 : 芝3走 + ダ2走、すべて1着（勝率1.0）
    - horse_1 / jockey_1 / trainer_1 : 芝3走、すべて8着（勝率0.0）

    horse_0 が並び順で先に来るため、バグがあると horse_1 の初戦が
    horse_0 の「勝率1.0」を拾う。期待値は NaN（過去走が無い）。
    距離・競馬場は1種類に固定し、複合キーの集計もエンティティ単位に潰している。
    """
    rows = []

    def add(idx: int, horse: str, surface: str, finish: int, day: int) -> None:
        rows.append(
            {
                "entry_id": f"e{idx}",
                "race_id_str": f"r{idx:03d}",
                "race_date": pd.Timestamp("2018-01-01") + pd.Timedelta(days=day),
                "racecourse_name": "東京",
                "surface": surface,
                "distance_m": 1600,
                "track_condition": "良",
                "weather": "晴",
                "direction": "左",
                "bracket_number": 1,
                "post_position": 1,
                "horse_age": 3,
                "weight_carried_kg": 55.0,
                "finish_position": finish,
                "last_3f_time": 34.0,
                "win_odds": 3.0,
                "win_favorite": 1,
                "horse_weight_kg": 480,
                "horse_weight_diff": 0,
                "prize_money_10k_yen": 100.0,
                "horse_uuid": horse,
                "horse_name": horse,
                "horse_sex": "牡",
                "jockey_uuid": f"jockey_{horse[-1]}",
                "jockey_name": f"J{horse[-1]}",
                "trainer_uuid": f"trainer_{horse[-1]}",
                "trainer_name": f"T{horse[-1]}",
                "race_uuid": f"ru{idx}",
            }
        )

    i = 0
    for d in range(3):  # horse_0 芝3走・全1着
        add(i, "horse_0", "芝", 1, d)
        i += 1
    for d in range(3, 5):  # horse_0 ダ2走・全1着
        add(i, "horse_0", "ダ", 1, d)
        i += 1
    for d in range(5, 8):  # horse_1 芝3走・全8着
        add(i, "horse_1", "芝", 8, d)
        i += 1

    df = pd.DataFrame(rows)
    df["race_date"] = pd.to_datetime(df["race_date"])
    for col in [
        "distance_m",
        "bracket_number",
        "post_position",
        "horse_age",
        "horse_weight_kg",
        "horse_weight_diff",
        "win_favorite",
        "finish_position",
    ]:
        df[col] = df[col].astype("Int64")
    return df


# 特徴量 → 本来の集計単位（このキーごとの先頭行は「過去走なし」= NaN であるべき）
GROUP_KEYS_BY_FEATURE = {
    # --- expanding 系（バグ時は全行が汚染された） ---
    "jockey_win_rate": ["jockey_uuid"],
    "jockey_place_rate": ["jockey_uuid"],
    "jockey_course_win_rate": ["jockey_uuid", "racecourse_name"],
    "jockey_distance_win_rate": ["jockey_uuid"],
    "trainer_win_rate": ["trainer_uuid"],
    "trainer_place_rate": ["trainer_uuid"],
    "trainer_course_win_rate": ["trainer_uuid", "racecourse_name"],
    "trainer_distance_win_rate": ["trainer_uuid"],
    "horse_surface_win_rate": ["horse_uuid", "surface"],
    "horse_surface_place_rate": ["horse_uuid", "surface"],
    "horse_track_cond_win_rate": ["horse_uuid", "track_condition"],
    "cumulative_prize": ["horse_uuid"],
    # --- rolling 系（バグ時は各グループ先頭 w-1 行が汚染された） ---
    "horse_avg_finish_3": ["horse_uuid"],
    "horse_avg_finish_5": ["horse_uuid"],
    "horse_avg_last3f_3": ["horse_uuid"],
    "horse_avg_last3f_5": ["horse_uuid"],
    "horse_win_rate_3": ["horse_uuid"],
    "horse_win_rate_5": ["horse_uuid"],
    "horse_place_rate_3": ["horse_uuid"],
    "horse_place_rate_5": ["horse_uuid"],
    "horse_avg_prize_3": ["horse_uuid"],
    "horse_avg_prize_5": ["horse_uuid"],
    "horse_surface_avg_finish": ["horse_uuid", "surface"],
    "horse_track_cond_avg_finish": ["horse_uuid", "track_condition"],
}


class TestGroupBoundaryLeakage:
    """集計特徴量が別のエンティティのデータを拾っていないことを検証する。"""

    @pytest.mark.parametrize(("feature", "keys"), sorted(GROUP_KEYS_BY_FEATURE.items()))
    def test_group_head_is_nan(self, feature: str, keys: list[str]) -> None:
        """各集計単位の初回行は、過去走が無いので NaN でなければならない。"""
        result = build_feature_matrix(_make_multi_entity_df())
        heads = (
            result.sort_values(keys + ["race_date", "race_id_str"])
            .groupby(keys, observed=True)
            .head(1)
        )
        bad = heads[heads[feature].notna()]
        assert bad.empty, (
            f"{feature}: 集計単位 {keys} の初回行が NaN でない "
            f"（別エンティティの値を拾っている）。値={bad[feature].tolist()}"
        )

    def test_losing_horse_not_contaminated_by_winner(self) -> None:
        """全敗の馬の勝率が、全勝の馬の値に引きずられないこと。"""
        result = build_feature_matrix(_make_multi_entity_df())
        h1 = result[result["horse_uuid"] == "horse_1"].sort_values(
            ["race_date", "race_id_str"]
        )
        # 2走目・3走目は過去走が全て8着なので勝率は厳密に 0.0
        assert h1.iloc[1]["horse_win_rate_3"] == 0.0, (
            f"2走目の勝率は 0.0 のはず。実際={h1.iloc[1]['horse_win_rate_3']}"
        )
        assert h1.iloc[2]["horse_win_rate_3"] == 0.0, (
            f"3走目の勝率は 0.0 のはず。実際={h1.iloc[2]['horse_win_rate_3']}"
        )
        assert h1.iloc[1]["jockey_win_rate"] == 0.0, (
            f"騎手の通算勝率も 0.0 のはず。実際={h1.iloc[1]['jockey_win_rate']}"
        )

    def test_cumulative_prize_is_per_horse(self) -> None:
        """通算賞金が全馬の累計になっていないこと（1走=100なので2走目は100）。"""
        result = build_feature_matrix(_make_multi_entity_df())
        h1 = result[result["horse_uuid"] == "horse_1"].sort_values(
            ["race_date", "race_id_str"]
        )
        assert h1.iloc[1]["cumulative_prize"] == 100.0, (
            f"2走目の通算賞金は 100.0 のはず。実際={h1.iloc[1]['cumulative_prize']}"
        )

    def test_correctly_grouped_features_stay_correct(self) -> None:
        """既に正しく groupby 内で計算されている特徴量の回帰ガード。"""
        result = build_feature_matrix(_make_multi_entity_df())
        h1 = result[result["horse_uuid"] == "horse_1"].sort_values(
            ["race_date", "race_id_str"]
        )
        assert h1.iloc[0]["race_count"] == 0
        assert h1.iloc[1]["race_count"] == 1
        assert pd.isna(h1.iloc[0]["days_since_last_race"])


class TestFeatureMatrixOrdering:
    """検証用分割が時間順になる前提（trainer.py が iloc で切るため）。"""

    def test_returned_rows_are_sorted_by_date(self) -> None:
        """
        build_feature_matrix の戻りは日付昇順であること。

        trainer.py は X_train.iloc[:90%] / iloc[90%:] で検証用を切り出し、
        コメントに "last 10% by time" と書いている。df が馬UUID順だと
        これは「時間順の末尾10%」ではなく「特定の馬の集まり」になる。

        ⚠️ 馬ごとに日付をまとめた合成データだと「馬UUID順＝日付順」に
        偶然一致して検出できない。ここでは日付を交互にして両者を食い違わせる。
        """
        base = _make_multi_entity_df()
        # horse_0 は偶数日、horse_1 は奇数日。行順(馬UUID順)に並べると
        # 0,2,4,6,8,1,3,5 となり日付昇順にならない。
        # ⚠️ 行の連番で採番すると馬ごとに日付が固まってしまい前提が崩れるので、
        #    馬ごとのカウンタで採番する（実際に一度これで失敗した）。
        interleaved = base.copy()
        counters: dict[str, int] = {}
        new_dates = []
        for h in interleaved["horse_uuid"]:
            n = counters.get(h, 0)
            counters[h] = n + 1
            offset = 0 if h == "horse_0" else 1
            new_dates.append(
                pd.Timestamp("2018-01-01") + pd.Timedelta(days=2 * n + offset)
            )
        interleaved["race_date"] = new_dates
        # 馬UUID順に並べた時点で日付が昇順でないことを前提として確認する
        by_horse = interleaved.sort_values(["horse_uuid", "race_date"])
        assert by_horse["race_date"].tolist() != sorted(
            by_horse["race_date"].tolist()
        ), "合成データの前提が崩れている（馬順と日付順が一致してしまっている）"

        result = build_feature_matrix(interleaved)
        dates = result["race_date"].tolist()
        assert dates == sorted(dates), (
            "日付昇順でない。trainer.py の iloc による検証用分割が時間順にならない"
        )
