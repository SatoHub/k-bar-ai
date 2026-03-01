"""
Feature engineering for horse racing prediction.

Loads raw data from the database, computes rolling/cumulative statistics,
and produces a feature matrix ready for LightGBM training or prediction.
All rolling features use shift(1) to prevent future data leakage.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import create_engine, text

from app.config import settings
from app.ml.config import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    HORSE_ROLLING_WINDOWS,
    TARGET_COLUMN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_RAW_SQL_BASE = """
    SELECT
        re.id          AS entry_id,
        r.race_id      AS race_id_str,
        r.race_date,
        r.racecourse_name,
        r.surface,
        r.distance_m,
        r.track_condition,
        r.weather,
        r.direction,
        re.bracket_number,
        re.post_position,
        re.horse_age,
        re.weight_carried_kg,
        re.finish_position,
        re.last_3f_time,
        re.win_odds,
        re.win_favorite,
        re.horse_weight_kg,
        re.horse_weight_diff,
        re.prize_money_10k_yen,
        h.id   AS horse_uuid,
        h.name AS horse_name,
        h.sex  AS horse_sex,
        j.id   AS jockey_uuid,
        j.name AS jockey_name,
        t.id   AS trainer_uuid,
        t.name AS trainer_name,
        r.id   AS race_uuid
    FROM race_entries re
    JOIN races    r ON r.id  = re.race_id
    JOIN horses   h ON h.id  = re.horse_id
    LEFT JOIN jockeys  j ON j.id  = re.jockey_id
    LEFT JOIN trainers t ON t.id  = re.trainer_id
    {where_clause}
    ORDER BY r.race_date, r.race_id, COALESCE(re.finish_position, 999)
"""


def _load_raw_data(include_upcoming: bool = False) -> pd.DataFrame:
    """Load all race entries joined with master tables.

    Args:
        include_upcoming: If True, also loads entries without finish_position
            (upcoming races for prediction). Default False for training.
    """
    if include_upcoming:
        where_clause = ""
    else:
        where_clause = "WHERE re.finish_position IS NOT NULL"
    sql = text(_RAW_SQL_BASE.format(where_clause=where_clause))
    engine = create_engine(settings.database_url_sync)
    logger.info("Loading raw data from database...")
    df = pd.read_sql(sql, engine)
    logger.info("Loaded %d rows", len(df))
    engine.dispose()

    # Type conversions
    df["race_date"] = pd.to_datetime(df["race_date"])
    for col in ["weight_carried_kg", "last_3f_time", "win_odds", "prize_money_10k_yen"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in [
        "finish_position",
        "bracket_number",
        "post_position",
        "horse_age",
        "horse_weight_kg",
        "horse_weight_diff",
        "win_favorite",
        "distance_m",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    return df


# ---------------------------------------------------------------------------
# Horse rolling statistics
# ---------------------------------------------------------------------------


def _compute_horse_rolling_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-horse rolling statistics over past races.

    Uses shift(1) so that each row only sees stats from PRIOR races,
    preventing future data leakage.
    """
    df = df.sort_values(["horse_uuid", "race_date", "race_id_str"]).copy()

    # Binary flags for win / place
    df["is_win"] = (df["finish_position"] == 1).astype("float64")
    df["is_place"] = (df["finish_position"] <= 3).astype("float64")

    grouped = df.groupby("horse_uuid")

    for w in HORSE_ROLLING_WINDOWS:
        # shift(1) ensures current race is excluded
        finish_shifted = grouped["finish_position"].shift(1)
        last3f_shifted = grouped["last_3f_time"].shift(1)
        win_shifted = grouped["is_win"].shift(1)
        place_shifted = grouped["is_place"].shift(1)
        prize_shifted = grouped["prize_money_10k_yen"].shift(1)

        df[f"horse_avg_finish_{w}"] = finish_shifted.rolling(w, min_periods=1).mean()
        df[f"horse_avg_last3f_{w}"] = last3f_shifted.rolling(w, min_periods=1).mean()
        df[f"horse_win_rate_{w}"] = win_shifted.rolling(w, min_periods=1).mean()
        df[f"horse_place_rate_{w}"] = place_shifted.rolling(w, min_periods=1).mean()
        df[f"horse_avg_prize_{w}"] = prize_shifted.rolling(w, min_periods=1).mean()

    return df


# ---------------------------------------------------------------------------
# Jockey cumulative statistics
# ---------------------------------------------------------------------------


def _compute_jockey_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute cumulative jockey statistics with expanding window + shift(1)."""
    df = df.sort_values(["jockey_uuid", "race_date", "race_id_str"]).copy()

    grouped = df.groupby("jockey_uuid")

    win_shifted = grouped["is_win"].shift(1)
    place_shifted = grouped["is_place"].shift(1)

    df["jockey_win_rate"] = win_shifted.expanding(min_periods=1).mean()
    df["jockey_place_rate"] = place_shifted.expanding(min_periods=1).mean()

    # Jockey × course
    df = df.sort_values(["jockey_uuid", "racecourse_name", "race_date", "race_id_str"])
    jc_grouped = df.groupby(["jockey_uuid", "racecourse_name"])
    jc_win_shifted = jc_grouped["is_win"].shift(1)
    df["jockey_course_win_rate"] = jc_win_shifted.expanding(min_periods=1).mean()

    # Jockey × distance band (short/mile/mid/long)
    df["distance_band"] = pd.cut(
        df["distance_m"],
        bins=[0, 1400, 1800, 2200, 9999],
        labels=["short", "mile", "mid", "long"],
    )
    df = df.sort_values(["jockey_uuid", "distance_band", "race_date", "race_id_str"])
    jd_grouped = df.groupby(["jockey_uuid", "distance_band"], observed=True)
    jd_win_shifted = jd_grouped["is_win"].shift(1)
    df["jockey_distance_win_rate"] = jd_win_shifted.expanding(min_periods=1).mean()

    df.drop(columns=["distance_band"], inplace=True)
    return df


# ---------------------------------------------------------------------------
# Trainer cumulative statistics
# ---------------------------------------------------------------------------


def _compute_trainer_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute cumulative trainer statistics with expanding window + shift(1)."""
    df = df.sort_values(["trainer_uuid", "race_date", "race_id_str"]).copy()

    grouped = df.groupby("trainer_uuid")
    win_shifted = grouped["is_win"].shift(1)
    place_shifted = grouped["is_place"].shift(1)

    df["trainer_win_rate"] = win_shifted.expanding(min_periods=1).mean()
    df["trainer_place_rate"] = place_shifted.expanding(min_periods=1).mean()

    # Trainer × course
    df = df.sort_values(["trainer_uuid", "racecourse_name", "race_date", "race_id_str"])
    tc_grouped = df.groupby(["trainer_uuid", "racecourse_name"])
    tc_win_shifted = tc_grouped["is_win"].shift(1)
    df["trainer_course_win_rate"] = tc_win_shifted.expanding(min_periods=1).mean()

    # Trainer × distance band (short/mile/mid/long)
    df["distance_band"] = pd.cut(
        df["distance_m"],
        bins=[0, 1400, 1800, 2200, 9999],
        labels=["short", "mile", "mid", "long"],
    )
    df = df.sort_values(["trainer_uuid", "distance_band", "race_date", "race_id_str"])
    td_grouped = df.groupby(["trainer_uuid", "distance_band"], observed=True)
    td_win_shifted = td_grouped["is_win"].shift(1)
    df["trainer_distance_win_rate"] = td_win_shifted.expanding(min_periods=1).mean()
    df.drop(columns=["distance_band"], inplace=True)

    return df


# ---------------------------------------------------------------------------
# Horse × surface / track condition statistics
# ---------------------------------------------------------------------------


def _compute_horse_surface_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-horse stats grouped by surface (芝/ダート)."""
    df = df.sort_values(["horse_uuid", "surface", "race_date", "race_id_str"]).copy()
    hs_grouped = df.groupby(["horse_uuid", "surface"], observed=True)

    win_shifted = hs_grouped["is_win"].shift(1)
    place_shifted = hs_grouped["is_place"].shift(1)
    finish_shifted = hs_grouped["finish_position"].shift(1)

    df["horse_surface_win_rate"] = win_shifted.expanding(min_periods=1).mean()
    df["horse_surface_place_rate"] = place_shifted.expanding(min_periods=1).mean()
    df["horse_surface_avg_finish"] = finish_shifted.rolling(5, min_periods=1).mean()

    return df


def _compute_horse_track_condition_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-horse stats grouped by track condition (良/稍/重/不良)."""
    df = df.sort_values(
        ["horse_uuid", "track_condition", "race_date", "race_id_str"]
    ).copy()
    htc_grouped = df.groupby(["horse_uuid", "track_condition"], observed=True)

    win_shifted = htc_grouped["is_win"].shift(1)
    finish_shifted = htc_grouped["finish_position"].shift(1)

    df["horse_track_cond_win_rate"] = win_shifted.expanding(min_periods=1).mean()
    df["horse_track_cond_avg_finish"] = finish_shifted.rolling(5, min_periods=1).mean()

    return df


# ---------------------------------------------------------------------------
# Horse condition features
# ---------------------------------------------------------------------------


def _compute_horse_condition_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute days since last race, cumulative prize, race count."""
    df = df.sort_values(["horse_uuid", "race_date", "race_id_str"]).copy()

    grouped = df.groupby("horse_uuid")

    # Days since last race
    prev_date = grouped["race_date"].shift(1)
    df["days_since_last_race"] = (df["race_date"] - prev_date).dt.days.astype("float64")

    # Cumulative prize (sum of all prior races, excluding current)
    prize_shifted = grouped["prize_money_10k_yen"].shift(1)
    df["cumulative_prize"] = prize_shifted.expanding(min_periods=1).sum()

    # Cumulative race count (prior races)
    df["race_count"] = grouped.cumcount()  # 0-indexed = number of prior races

    return df


# ---------------------------------------------------------------------------
# Categorical encoding
# ---------------------------------------------------------------------------


def _encode_categorical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert categorical columns to pandas Categorical (LightGBM native support)."""
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_feature_matrix(
    df: pd.DataFrame | None = None,
    include_upcoming: bool = False,
) -> pd.DataFrame:
    """
    Build the complete feature matrix.

    If df is None, loads from database. Otherwise uses the provided DataFrame
    (useful for testing).

    Args:
        include_upcoming: If True, also loads upcoming races (no finish_position)
            for prediction. Rolling stats will use only prior finished races.

    Returns a DataFrame with FEATURE_COLUMNS + CATEGORICAL_COLUMNS + TARGET_COLUMN
    plus metadata columns (entry_id, race_id_str, race_date, horse_uuid, etc.).
    """
    if df is None:
        df = _load_raw_data(include_upcoming=include_upcoming)

    logger.info("Computing horse rolling stats...")
    df = _compute_horse_rolling_stats(df)
    logger.info("Computing jockey stats...")
    df = _compute_jockey_stats(df)
    logger.info("Computing trainer stats...")
    df = _compute_trainer_stats(df)
    logger.info("Computing horse surface stats...")
    df = _compute_horse_surface_stats(df)
    logger.info("Computing horse track condition stats...")
    df = _compute_horse_track_condition_stats(df)
    logger.info("Computing horse condition features...")
    df = _compute_horse_condition_features(df)
    logger.info("Encoding categorical features...")
    df = _encode_categorical_features(df)

    # Ensure target column exists
    if TARGET_COLUMN not in df.columns:
        df[TARGET_COLUMN] = (df["finish_position"] <= 3).astype("float64")

    all_features = FEATURE_COLUMNS + CATEGORICAL_COLUMNS
    missing = [c for c in all_features if c not in df.columns]
    if missing:
        logger.warning("Missing feature columns: %s", missing)

    logger.info(
        "Feature matrix ready: %d rows, %d feature columns, NaN ratio: %.2f%%",
        len(df),
        len(all_features),
        df[all_features].isna().mean().mean() * 100,
    )
    return df
