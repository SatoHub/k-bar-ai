"""
CSV column name (Japanese) to internal field name mapping
for all 66 columns of the Kaggle JRA dataset.
"""

# CSV Japanese column name -> internal name
COLUMN_MAP: dict[str, str] = {
    # col 1 - composite key (ignored, we build our own)
    "レース馬番ID": "race_pp_id",
    # col 2
    "レースID": "race_id",
    # col 3 - YYYYMMDD format
    "レース日付": "race_date",
    # col 4
    "開催回数": "meeting_number",
    # col 5
    "競馬場コード": "racecourse_code",
    # col 6
    "競馬場名": "racecourse_name",
    # col 7
    "開催日数": "racing_day_number",
    # Race symbol flags (cols 8-28) -> pack into race_symbols JSONB
    "競争条件": "race_condition",
    "レース記号/[抽]": "sym_drawing",
    "レース記号/(馬齢)": "sym_age",
    "レース記号/牝": "sym_mare",
    "レース記号/(父)": "sym_sire",
    "レース記号/(別定)": "sym_special_weight",
    "レース記号/(混)": "sym_mixed",
    "レース記号/(ハンデ)": "sym_handicap",
    "レース記号/(抽)": "sym_drawing_jra",
    "レース記号/(市)": "sym_market",
    "レース記号/(定量)": "sym_fixed_weight",
    "レース記号/牡": "sym_stallion",
    "レース記号/関東配布馬": "sym_kanto_dist",
    "レース記号/(指)": "sym_specified",
    "レース記号/関西配布馬": "sym_kansai_dist",
    "レース記号/九州産馬": "sym_kyushu_bred",
    "レース記号/見習騎手": "sym_apprentice",
    "レース記号/せん": "sym_gelding",
    "レース記号/(国際)": "sym_international",
    "レース記号/[指]": "sym_specified_local",
    "レース記号/(特指)": "sym_special_specified",
    # Race details (cols 29-42)
    "レース番号": "race_number",
    "重賞回次": "graded_race_edition",
    "レース名": "race_name",
    # G1/G2/G3/Listed/blank
    "リステッド・重賞競走": "graded_race",
    "障害区分": "steeplechase_category",
    "芝・ダート区分": "surface",
    "芝・ダート区分2": "surface2",
    "右左回り・直線区分": "direction",
    "内・外・襷区分": "course_config",
    "距離(m)": "distance_m",
    "天候": "weather",
    "馬場状態1": "track_condition",
    "馬場状態2": "track_condition2",
    "発走時刻": "post_time",
    # Results & Horse info (cols 43-56)
    "着順": "finish_position",
    "着順注記": "finish_note",
    "枠番": "bracket_number",
    "馬番": "post_position",
    "馬名": "horse_name",
    "性別": "sex",
    "馬齢": "age",
    "斤量": "weight_carried_kg",
    "騎手": "jockey_name",
    # tenths of second
    "タイム": "total_time_tenths",
    "着差": "margin",
    "1コーナー": "corner_pos_1",
    "2コーナー": "corner_pos_2",
    "3コーナー": "corner_pos_3",
    # Performance & Betting (cols 57-62)
    "4コーナー": "corner_pos_4",
    "上り": "last_3f_time",
    "単勝": "win_odds",
    "人気": "win_favorite",
    "馬体重": "horse_weight_kg",
    "馬体重増減": "horse_weight_diff",
    # Connections (cols 63-66)
    "東西・外国・地方区分": "trainer_region",
    "調教師": "trainer_name",
    "馬主": "owner",
    "賞金(万円)": "prize_money_10k_yen",
}

# Columns whose values are race symbol flags (to be packed into JSONB)
RACE_SYMBOL_COLUMNS = [k for k, v in COLUMN_MAP.items() if v.startswith("sym_")]
