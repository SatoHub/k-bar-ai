"""ML configuration constants."""

from pathlib import Path

# --- Paths ---
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
MODELS_DIR.mkdir(exist_ok=True)

# --- Feature engineering ---
HORSE_ROLLING_WINDOWS = [3, 5]

FEATURE_COLUMNS = [
    # Horse rolling stats
    "horse_avg_finish_3",
    "horse_avg_finish_5",
    "horse_avg_last3f_3",
    "horse_avg_last3f_5",
    "horse_win_rate_3",
    "horse_win_rate_5",
    "horse_place_rate_3",
    "horse_place_rate_5",
    "horse_avg_prize_3",
    "horse_avg_prize_5",
    # Jockey stats
    "jockey_win_rate",
    "jockey_place_rate",
    "jockey_course_win_rate",
    "jockey_distance_win_rate",
    # Trainer stats
    "trainer_win_rate",
    "trainer_place_rate",
    "trainer_course_win_rate",
    # Horse condition
    "days_since_last_race",
    "cumulative_prize",
    "race_count",
    # Race info (numeric)
    "distance_m",
    "bracket_number",
    "post_position",
    "horse_age",
    "weight_carried_kg",
    "horse_weight_kg",
    "horse_weight_diff",
    "win_odds",
    "win_favorite",
]

CATEGORICAL_COLUMNS = [
    "surface",
    "track_condition",
    "weather",
    "direction",
    "racecourse_name",
    "horse_sex",
]

TARGET_COLUMN = "is_place"  # 複勝圏内 (finish_position <= 3)

# --- LightGBM ---
LGBM_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "seed": 42,
}

LGBM_NUM_BOOST_ROUND = 1000
LGBM_EARLY_STOPPING_ROUNDS = 50

# --- Train/Test split ---
DEFAULT_CUTOFF_YEAR = 2020  # train: <2020, test: >=2020

# --- SHAP explanation ---
TOP_SHAP_FEATURES = 5

# Feature name → Japanese label mapping for SHAP explanations
FEATURE_LABEL_JA = {
    "horse_avg_finish_3": "直近3走の平均着順",
    "horse_avg_finish_5": "直近5走の平均着順",
    "horse_avg_last3f_3": "直近3走の平均上がり3F",
    "horse_avg_last3f_5": "直近5走の平均上がり3F",
    "horse_win_rate_3": "直近3走の勝率",
    "horse_win_rate_5": "直近5走の勝率",
    "horse_place_rate_3": "直近3走の複勝率",
    "horse_place_rate_5": "直近5走の複勝率",
    "horse_avg_prize_3": "直近3走の平均賞金",
    "horse_avg_prize_5": "直近5走の平均賞金",
    "jockey_win_rate": "騎手の通算勝率",
    "jockey_place_rate": "騎手の通算複勝率",
    "jockey_course_win_rate": "騎手の当コース勝率",
    "jockey_distance_win_rate": "騎手の当距離帯勝率",
    "trainer_win_rate": "調教師の通算勝率",
    "trainer_place_rate": "調教師の通算複勝率",
    "trainer_course_win_rate": "調教師の当コース勝率",
    "days_since_last_race": "前走からの間隔日数",
    "cumulative_prize": "通算賞金",
    "race_count": "通算出走回数",
    "distance_m": "距離",
    "bracket_number": "枠番",
    "post_position": "馬番",
    "horse_age": "馬齢",
    "weight_carried_kg": "斤量",
    "horse_weight_kg": "馬体重",
    "horse_weight_diff": "馬体重増減",
    "win_odds": "単勝オッズ",
    "win_favorite": "人気順",
    "surface": "芝/ダート",
    "track_condition": "馬場状態",
    "weather": "天候",
    "direction": "回り",
    "racecourse_name": "競馬場",
    "horse_sex": "性別",
}
