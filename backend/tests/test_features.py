"""Tests for feature engineering — especially future data leakage prevention."""

import numpy as np
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
            rows.append({
                "entry_id": f"entry_{h}_{r}",
                "race_id_str": f"race_{r}",
                "race_date": pd.Timestamp(f"2020-01-{r+1:02d}"),
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
            })
    df = pd.DataFrame(rows)
    df["race_date"] = pd.to_datetime(df["race_date"])
    for col in ["distance_m", "bracket_number", "post_position",
                "horse_age", "horse_weight_kg", "horse_weight_diff",
                "win_favorite", "finish_position"]:
        df[col] = df[col].astype("Int64")
    return df


class TestHorseRollingStats:
    """Verify that horse rolling stats use shift(1) to prevent leakage."""

    def test_first_race_has_nan(self):
        """Horse's first race should have NaN rolling stats (no prior data)."""
        df = _make_sample_df(n_horses=1, races_per_horse=5)
        result = _compute_horse_rolling_stats(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert pd.isna(first_row["horse_avg_finish_3"]), \
            "First race should have NaN for rolling avg (no prior data)"

    def test_no_current_race_in_rolling(self):
        """Rolling stats for race N should NOT include race N's result."""
        df = _make_sample_df(n_horses=1, races_per_horse=6)
        result = _compute_horse_rolling_stats(df)

        horse_rows = result[result["horse_uuid"] == "horse_0"].reset_index(drop=True)

        # Row index 3 (4th race): rolling-3 should use races 1,2,3 (indices 0,1,2)
        # finish_position pattern: 1,2,3,4,5,1,...  so races 0,1,2 = [1,2,3]
        row3 = horse_rows.iloc[3]
        expected_avg = np.mean([1, 2, 3])  # indices 0,1,2
        assert abs(row3["horse_avg_finish_3"] - expected_avg) < 0.01, \
            f"Expected avg={expected_avg}, got {row3['horse_avg_finish_3']}"

    def test_rolling_window_respects_size(self):
        """Rolling-5 with only 3 prior races should still work (min_periods=1)."""
        df = _make_sample_df(n_horses=1, races_per_horse=5)
        result = _compute_horse_rolling_stats(df)

        horse_rows = result[result["horse_uuid"] == "horse_0"].reset_index(drop=True)

        # Row 3 has 3 prior races, rolling-5 with min_periods=1 should use all 3
        row3 = horse_rows.iloc[3]
        assert not pd.isna(row3["horse_avg_finish_5"]), \
            "Rolling-5 should work with fewer than 5 prior races"


class TestJockeyStats:
    """Verify jockey cumulative stats use shift(1)."""

    def test_first_ride_has_nan(self):
        """Jockey's first ride should have NaN cumulative stats."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_jockey_stats(df)

        first_row = result.iloc[0]
        assert pd.isna(first_row["jockey_win_rate"]), \
            "Jockey's first ride should have NaN win rate"


class TestTrainerStats:
    """Verify trainer cumulative stats use shift(1)."""

    def test_first_entry_has_nan(self):
        """Trainer's first entry should have NaN cumulative stats."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_trainer_stats(df)

        first_row = result.iloc[0]
        assert pd.isna(first_row["trainer_win_rate"]), \
            "Trainer's first entry should have NaN win rate"


class TestHorseCondition:
    """Verify horse condition features."""

    def test_first_race_no_days_since(self):
        """First race should have NaN days_since_last_race."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_horse_condition_features(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert pd.isna(first_row["days_since_last_race"]), \
            "First race should have NaN days_since_last_race"

    def test_race_count_starts_at_zero(self):
        """race_count for the first entry should be 0 (no prior races)."""
        df = _make_sample_df(n_horses=1, races_per_horse=3)
        df["is_win"] = (df["finish_position"] == 1).astype("float64")
        df["is_place"] = (df["finish_position"] <= 3).astype("float64")
        result = _compute_horse_condition_features(df)

        first_row = result[result["horse_uuid"] == "horse_0"].iloc[0]
        assert first_row["race_count"] == 0, \
            "First race should have race_count=0"


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
