# バグレジストリ — K-Bar AI

> 本番環境で発覚したバグと対応状況の記録。
> E2Eヘルスチェック (`frontend/e2e/production-health-check.spec.ts`) で再発を自動検知する。

---

## 確認済みバグ

| バグID | 発覚日 | 概要 | 原因 | 修正ファイル | E2Eチェック項目 | ステータス |
|--------|--------|------|------|-------------|----------------|-----------|
| BUG-001 | 2026-02-28 | AI予想が全レースで欠落 | (1)`.gitignore`でモデルファイル除外→VPSに届かない (2)`libgomp1`未インストール→LightGBM実行不可 | `.gitignore`, `Dockerfile.backend`, `docker-compose.prod.yml`, `docker-entrypoint.sh` | 全レースで `/api/v1/predictions/{race_id}` が空でないこと | **修正済み・デプロイ済み** |
| BUG-002 | 2026-02-28 | 出走馬の重複/ゴーストエントリ | (1)取消馬の削除ロジック不在 (2)再スクレイピング未実行で削除ロジックが発火しない | `backend/app/scraper/store.py`, `backend/app/scheduler/jobs.py` | entries数 == head_count, post_position非null, 同一race内でpost_position重複なし | **修正済み・デプロイ済み** |
| BUG-003 | 2026-02-28 | オッズが一部レースのみ取得 | オッズパーサーが `"middle"` / `"yoso"` ステータスのレースページを拒否していた | `backend/app/scraper/parsers/odds.py` | 全レースで `/api/v1/races/{race_id}/odds` が空でないこと | **修正済み** |

---

## 予防的チェック項目

| チェックID | 概要 | 検証内容 | E2Eテスト |
|-----------|------|---------|----------|
| PRV-001 | UIに「データなし」表示がないこと | データ取得失敗時にフォールバック表示が出る場合、本番ではデータが存在するはずなので警告扱い | UI上に「データがありません」「AI予想データがありません」系メッセージがないこと |
| PRV-002 | 払戻計算の正確性 | JRA端数処理 `Math.floor((amount * odds) / 100) * 100` と一致すること | シミュレーターで単勝選択→掛け金入力→推定払戻額が計算式と一致 |

---

## バグ詳細

### BUG-001: AI予想が全レースで欠落

**症状**: レース詳細ページに「AI予想データがありません」と表示。全レースで予想が0件。

**根本原因**:
1. LightGBMモデルファイル (`backend/models/*.joblib`) が `.gitignore` に含まれており、git経由でVPSにデプロイされなかった
2. `docker-compose.prod.yml` にモデルディレクトリのvolumeマウントが未設定だった
3. `docker-entrypoint.sh` でモデルファイルの存在チェックがなかった

**修正内容**:
- `.gitignore`: `backend/models/`の除外を解除し、`v1.0.0.joblib`をgit管理に追加
- `docker-compose.prod.yml`: `./backend/models:/app/models:ro` をvolumeに追加
- `docker-entrypoint.sh`: 起動時にモデルファイルの存在を確認するヘルスチェック追加
- `Dockerfile.backend`: `libgomp1`を追加（LightGBMのOpenMP依存）

---

### BUG-002: 出走馬の重複/ゴーストエントリ

**症状**: 出馬表に出走取消馬が残り、head_countとentries数が一致しない。28/36レースで計159件のゴーストエントリが発生。例: オーシャンS（中山11R）でマイネルジェロディとレッドシュヴェルトがpost_position=null, bracket_number=null, jockey=nullの状態で残存。

**根本原因**:
1. `store_shutuba()`に取消馬（post_position=null）のスキップ＆削除ロジックを追加済みだったが…
2. **再スクレイピングが実行されない**: `job_shutuba()`は`stub_only=True`または`entry_count < head_count`のレースのみ対象。既に出馬表取得済み（stub_only=False）かつentry_count >= head_countのレースは再スクレイピングされず、削除ロジックが発火しなかった
3. 出走取消前にスクレイプされた馬はpost_position付きでDBに保存され、取消後もDBに残り続けた

**修正内容**:
- `store.py`: `cleanup_scratched_entries()` — null post_positionのエントリを直接削除しhead_count更新
- `jobs.py`: `job_shutuba`完了後に各日付でクリーンアップ実行
- `jobs.py`: `job_data_integrity_check`（10:00 JST）でもクリーンアップ実行
- 初回デプロイ時に63件のゴーストエントリを削除完了

---

### BUG-003: オッズが一部レースのみ

**症状**: 36レース中、一部のレースでのみオッズが取得できている。

**根本原因**:
- `parsers/odds.py` がページステータス `"middle"`（レース途中）や `"yoso"` （予想段階）を「無効」として拒否していた
- 実際にはこれらのステータスでもオッズデータは存在する

**修正内容**:
- `parsers/odds.py`: 許可するステータスに `"middle"` と `"yoso"` を追加

---

## 運用ルール

1. **本番デプロイ前**: `npx playwright test e2e/production-health-check.spec.ts --project=PC` を必ず実行
2. **新バグ発覚時**: このファイルにバグIDを追番で追加し、対応するE2Eチェックを `production-health-check.spec.ts` に追加
3. **定期チェック**: 開催日の朝にヘルスチェックを実行し、データ完全性を確認
