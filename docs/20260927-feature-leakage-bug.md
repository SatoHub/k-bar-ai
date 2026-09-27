# 集計特徴量24個が「別の馬・別の騎手」のデータを拾っていた

発覚日: 2026-09-27（モデル性能の調査中に発見）

## 症状と原因

`features.py` は `shift(1)` を **groupby 内で正しく**行っていたが、
その後の `rolling` / `expanding` を **groupby の外**で呼んでいた。

```python
# 修正前
finish_shifted = grouped["finish_position"].shift(1)      # ← ここは馬ごとで正しい
df["horse_avg_finish_3"] = finish_shifted.rolling(3).mean()  # ★全体に対する rolling
```

`grouped[col].shift(1)` は df と同じ index を持つ**素の Series** を返す。
そこに `.rolling()` / `.expanding()` を直接かけると、窓がグループ境界をまたぐ。

pandas で再現して確認した実測値:

| 馬 | 修正前の値 | 本来の値 |
|---|---|---|
| horse_A（3走・全勝） | 1.0 / 1.0 | 1.0 / 1.0 |
| **horse_B の初出走** | **1.0** | **NaN** |
| horse_B の2走目 | 0.5 | 0.0 |

horse_B の初出走行が horse_A の勝率を拾っていた。

## 影響範囲

| 種類 | 数 | 影響 |
|---|---|---|
| `expanding` を groupby 外で呼んでいた | **12** | **全行が汚染。** 騎手・調教師の通算勝率は「データ全体の累積平均」になっており、**騎手固有の情報をほぼ持っていなかった**。`cumulative_prize` は全馬の賞金累計＝実質「行番号」 |
| `rolling` を groupby 外で呼んでいた | **12** | 各グループの先頭 w-1 行が直前グループのデータで汚染 |
| 正しかったもの | 約10 | `race_count`（`grouped.cumcount()`）・`days_since_last_race`・当日のレース情報 |

**未来情報リークにもなっていた。** 特徴量は `build_feature_matrix()` で
全期間まとめて計算してから時系列分割される（`trainer.py`）。`expanding` は
並び順の先頭から累積するため、UUID順で前にいるエンティティの
**2020年以降のレースが2019年以前の学習行の特徴量に混入**していた。

## 🔴 なぜ既存のテストで検出できなかったか

`backend/tests/test_features.py` には**リーク検査のテストが既にあった**。
しかし全て `n_horses=1`（単一の馬・騎手・調教師）で書かれていた。

**バグは「別のエンティティのデータを拾う」ものなので、
エンティティが1つしか無いテストでは構造的に検出できない。**

`test_build_from_provided_df` は2頭使っていたが、列の存在だけを検査し
値を検証していなかった。

> **「関数が呼べること」の検証と「境界で正しく切れていること」の検証は別物。**
> これは同日に certbot のスクリプトで踏んだ失敗
> （`docs/20260916-https-ip-certificate.md`）と**同じ構造**。
> コード内のコメント（"All rolling features use shift(1) to prevent
> future data leakage"）を検証の代わりにしてしまったのが共通の原因。
> → `~/.claude/CLAUDE.md` §12.2 に項目11として明文化した。

## 対処

1. **`_grouped_window()` ヘルパーに集約**し、全24箇所を groupby 内での
   `rolling`/`expanding` に修正（`features.py`）
2. **回帰テストを追加**（`tests/test_features.py::TestGroupBoundaryLeakage`）。
   2頭・2騎手・2調教師の合成データで「各集計単位の初回行は NaN」を
   24特徴量すべてについて検査。**修正前の実装では27件が落ちることを確認済み**
3. **検証用分割を日付ベースに修正**（`trainer.py`）。
   以前は `iloc[:90%]` の位置ベースで、df が馬UUID順だったため
   コメントの "last 10% by time" とは異なり「特定の馬の集まり」になっていた。
   `build_feature_matrix` の戻りも日付昇順に統一した
4. **サニティチェックを常設**（`app/ml/sanity.py`）。
   指標だけでは壊れた特徴量に気づけなかったので、
   「シャッフルしても AUC が落ちない特徴量＝実質機能していない」を自動検出する
5. **単勝 ROI を評価に追加**（`verifier.py`）。市場ベースライン（1番人気）と
   控除率の壁（80%）も併記し、「市場を超えているか」が一目で分かる形にした

## モデル性能への含意

- v1.0.0 → v1.1.0 で AUC が **+0.00004（実質ゼロ）** だった。
  v1.1.0 で追加した6特徴量（芝ダ別3・馬場状態別2・調教師距離帯1）は
  **6個すべてが汚染対象で、うち4個は「全行汚染」のグループ**だった。
  「特徴量を足しても効かない」のではなく「足した特徴量が計算されていなかった」
  可能性が高い
- したがって `docs/20260613-model-improvement-findings.md` の
  **「現行 v1.0.0 が実用上の天井に近い」という結論は、この前提の上で出されている。**
  修正後に再評価するまで天井かどうかは分からない

## ⚠️ 未実施（再学習がまだ）

修正時点で Docker（PostgreSQL）が起動しておらず、**再学習と AUC の
修正前後比較は未実施**。学習データ1.6万件…ではなく約161万件が DB 上にあるため、
ローカルDB無しでは学習できない。

再学習の手順:

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d
cd backend && uv run alembic upgrade head
# 新バージョンとして保存する（本番の v1.0.0 は差し替えない）
uv run python -m app.ml.trainer  # または make predict 相当のCLI
```

⚠️ **本番の `v1.0.0` を勝手に差し替えないこと。** 本番採用は
`backend/app/config.py` の `SCHED_PREDICT_MODEL_VERSION` で決まる。
切り替えはユーザー判断。
