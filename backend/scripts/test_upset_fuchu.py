"""Sanity test: score the 2026-06-21 府中牝馬S with the trained upset model.

Uses the real odds / popularity / main-model scores captured from production.
The race was a big upset (三連単106万), so a working model should flag it 高.
"""

from app.ml.upset_score import score_race

# (win_odds, win_favorite, predicted_score=p_main) per horse
FUCHU = [
    (3.3, 1, 0.4519),   # ヴァルキリーバース
    (5.0, 2, 0.3921),   # ニシノティアモ
    (8.7, 4, 0.2809),   # エストゥペンダ
    (9.4, 5, 0.2298),   # セキトバイースト (1着)
    (8.1, 3, 0.1915),   # コガネノソラ
    (9.9, 6, 0.1564),   # ルージュソリテール
    (20.0, 8, 0.1526),  # パラディレーヌ
    (24.6, 10, 0.1428), # マカナ (4着)
    (22.7, 9, 0.1221),  # ウイントワイライト (2着)
    (38.7, 12, 0.1015), # ホールネス
    (25.0, 11, 0.0962), # テレサ
    (15.0, 7, 0.0590),  # テリオスララ
    (54.5, 13, 0.0546), # ビップデイジー
    (140.7, 15, 0.0287),# ブラウンラチェット
    (215.2, 16, 0.0262),# セントメモリーズ
    (94.6, 14, 0.0214), # ミアネーロ (3着)
]

entries = [
    {"win_odds": o, "win_favorite": f, "predicted_score": p} for o, f, p in FUCHU
]

result = score_race(entries)
print("府中牝馬S 荒れ度:", result)
