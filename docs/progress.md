# 競馬AI予想アプリ 進捗管理

**最終更新:** 2026-06-09（JRA-VAN接続 完全成功 / 次回はjrvltsqlで本格DB化）

---

## 🔵 次回セッション開始ガイド（RESUME HERE）

### いまどこ？
**JRA-VAN接続をゼロから完成させた。** 契約→利用キー→JV-Linkインストール→32bit Python環境→
**実データ取得まで成功済み**（`backend/jravan/connect_test.py` で `JVOpen rc=0` 確認）。
> 目的: 普段のnetkeibaスクレイピングに加え、JRA-VANの正確なデータ（レース/オッズ/馬場）で精度補強する。

### 次にやること = jrvltsql で本格DB化（データ・オッズ取得の本番化）
`miyamamoto/jrvltsql`（JV-Link→DB化ツール）を使い、JRA-VANデータをDBに溜める。
手順書: `backend/jravan/jrvltsql-setup.md`

**推奨の進め方（安全策）:**
1. まず **SQLite + 直近1ヶ月** で動作確認（jrvltsqlのパイプラインが通るか）
   ```powershell
   # 32bit venvを有効化してから
   cd C:\Users\unoen\projects\k-bar-ai\backend\jravan
   .\.venv32\Scripts\Activate.ps1
   # jrvltsqlをclone & install（初回のみ）
   git clone https://github.com/miyamamoto/jrvltsql.git
   cd jrvltsql; pip install -e .
   quickstart_timeseries.bat --db sqlite --from 20260509 --to 20260609
   ```
2. OKなら **本番 PostgreSQL でフルセットアップ**（`kbar-postgres` が localhost:5432 で稼働中）
   ```sql
   CREATE DATABASE kbar_jravan;
   ```
   ```powershell
   $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_PORT="5432"
   $env:POSTGRES_DATABASE="kbar_jravan"; $env:POSTGRES_USER="..."; $env:POSTGRES_PASSWORD="..."
   quickstart_timeseries.bat --db postgresql --from 20210101 --to 20260609
   ```
   → オッズは `NL_O1`〜`NL_O6`（確定）/ `TS_O1`,`TS_O2`（時系列）/ `TS_SOKUHO_O1`〜（速報）に入る
3. 日次同期 `daily_sync.bat --db postgresql` をWindowsタスクスケジューラ登録

### 開始時に決める2点
- **取得期間**: Kaggleが1986〜2021 → 空白の **2021〜2026** を埋めるのが有力
- **保存先**: `kbar-postgres`（localhost:5432）内に専用DB **`kbar_jravan`**（アプリDBと分離）

### 環境メモ（再起動後そのまま使える）
- JV-Link: `C:\Program Files (x86)\JRA-VAN\Data Lab`（キー登録済み・要件OK）
- 32bit Python: `py -3.12-32`、venv: `backend/jravan/.venv32`（pywin32導入済み）
- 利用キー: `backend/jravan/.env`（gitignore済み・`JRAVAN_SERVICE_KEY`）
- 疎通再確認: `& backend\jravan\.venv32\Scripts\python.exe -u backend\jravan\connect_test.py`
- ⚠️ JV-Linkは**32bit Pythonでのみ**呼べる（`python`直打ちはStoreスタブに注意、`py`を使う）

### この先の最終ゴール（連携）
ステージング(`kbar_jravan`) → 本番VPSへ差分連携 → netkeibaデータとID突合 → 学習特徴量に追加（Step 6と合流）。
当日リアルタイムのオッズ/馬場は引き続きnetkeiba（VPS完結）、JRA-VANは正確な確定・過去データ補強が役割。

---

## 直近の作業内容（2026-02-23 〜 2026-03-01）

本番デプロイ後の安定化フェーズ。E2Eヘルスチェックで本番バグを検知 → 修正のループを回した。

### 本番バグ修正（バグレジストリ: `docs/20260228-bug-registry.md`）
- [x] **BUG-001** AI予想が全レースで欠落 — `.gitignore`でモデル除外＋`libgomp1`未導入 → 修正・デプロイ済み（`3c39771`他）
- [x] **BUG-002** 出走取消馬のゴーストエントリ重複 — 自動クリーンアップ実装で完全修正（`aa5450a`）
- [x] **BUG-003** オッズが一部レースのみ取得 — パーサーが`middle`/`yoso`ステータスを拒否していた問題を修正

### スクレイパー・スケジューラ強化
- [x] スクレイパーの信頼性を大幅強化（`bfc7b04`）
- [x] Playwright `--single-process` 除去でブラウザクラッシュ修正（`7cb0b85`）
- [x] スケジューラ自動化パイプライン修正＋朝のAI予想スケジュール追加（`1bab3d2`, `b568a0b`）
- [x] RaceEntry重複バグ修正・予測保存時の重複データエラー修正（`b568a0b`, `f512abc`）
- [x] 不完全エントリーの出馬表を再取得対象に含める（`48d21a0`）
- [x] 本番ヘルスチェック（`frontend/e2e/production-health-check.spec.ts`）追加

### モデル再学習（Step 6 の一部に着手）
- [x] **v1.1.0** 再学習 — 芝ダ別・馬場状態別・調教師距離帯の特徴量6つ追加（`3c39771`）
- [x] `backend/models/v1.1.0.joblib` 生成済み（v1.0.0と併存）

### フロント・デプロイ基盤
- [x] 馬券シミュレーターにボックス・フォーメーション・流し買い対応（`f5ab41b`）
- [x] AI成績ページSP版の横オーバーフロー修正（`d7f6e89`）
- [x] deploy.yml の git権限エラー・キャッシュ問題を解消（`06c799f`, `72f3735`, `eeeba75`）

### JRA-VAN連携（Step D/E）— 着手（2026-06-09）
- [x] **Step D 調査:** JV-Link接続方式・料金・Python連携を調査 → `docs/20260609-jravan-connection.md`
  - 結論: JV-LinkはWindows/COM専用 → 方式C（自宅PC週1同期）が必然。Data Lab.月2,090円。`miyamamoto/jrvltsql`(Apache-2.0)が要件に最も近い第一候補
- [x] **Step E リマインダー:** `job_jravan_reminder` 実装（週次LINE通知、`jobs.py`）
  - `SCHED_JRAVAN_REMINDER_ENABLED`(既定False)で制御。契約後に有効化 → 金9:00に同期リマインダー送信
- [x] **Step D 契約・JV-Link導入・疎通成功（2026-06-09）**
  - Data Lab.契約済み・利用キー取得済み・JV-Link(`C:\Program Files (x86)\JRA-VAN\Data Lab`)インストール済み
  - 自宅PCに32bit Python(3.12-32)+pywin32環境を構築 → `backend/jravan/connect_test.py` で疎通成功
  - `JVOpen rc=0` で認証OK、実データ(type=JG等)取得を確認。利用キーは`.env`管理(gitignore)
- [ ] **Step D 本実装(次):** `jrvltsql` で初回フルセットアップ → PostgreSQL(`kbar_jravan`)化 → 本番VPS差分連携・ID突合

### 次にやること
- [ ] v1.1.0 の本番予想精度を v1.0.0 と比較・検証
- [ ] **Step 6（MLOps）本格化:** モデル自動再学習・バージョン自動切り替えの仕組み化
- [ ] LINE通知拡張（Step 5）のpostbackボタン本番動作確認

---

## 過去セッション（2026-02-22 第2回）の作業内容

### LINE通知機能拡張（Step 4-6: 週次レポート・ハズレ原因・月次改善提案）

**完了:**
- [x] 新モデル: `MissReasonLog`（ハズレ原因記録）、`ImprovementProposal`（改善提案）
- [x] Alembicマイグレーション `c3d4e5f6a789` 作成（miss_reason_logs, improvement_proposals）
- [x] `config.py` に週次レポート・月次提案・将来用設定6項目追加
- [x] `weekly_report_service.py` 新規: 過去7日間の賭け・AI的中率集計
- [x] `monthly_proposal_service.py` 新規: ルールベース改善提案生成（再学習推奨・馬場別分析・トレンド）
- [x] `line_templates.py` 拡張: `build_weekly_report_flex()` にbet_type別的中率表示追加
- [x] `line_templates.py` 新規: `build_miss_reason_flex()`, `build_monthly_proposal_flex()`
- [x] `notification_service.py` に `push_miss_confirmation()`, `push_monthly_proposal()` 追加
- [x] `jobs.py`: 週次レポートジョブ（月曜8:00）、月次提案ジョブ（毎月1日8:00）追加
- [x] `jobs.py`: `job_notify_results` にハズレ確認送信（複勝ハズレのAI1位、最大3件）追加
- [x] `notifications.py`: PostbackEvent ハンドラに `miss_reason`/`proposal_response` 処理追加
- [x] 将来用: `SCHED_QUARTERLY_SUMMARY_ENABLED`, `JRAVAN_REMINDER_MONTH` + TODOコメント
- [x] 全ファイル構文チェック通過

**新規ファイル:**
- `backend/app/models/miss_reason.py`
- `backend/app/models/improvement_proposal.py`
- `backend/app/services/weekly_report_service.py`
- `backend/app/services/monthly_proposal_service.py`
- `backend/alembic/versions/c3d4e5f6a789_add_miss_reason_and_proposals.py`

**変更ファイル:**
- `backend/app/models/__init__.py` — 2モデル登録
- `backend/app/config.py` — 6設定追加
- `backend/app/scheduler/jobs.py` — 3ジョブ追加 + results拡張
- `backend/app/services/notification_service.py` — 2メソッド追加
- `backend/app/services/line_templates.py` — 3テンプレート追加 + 1拡張
- `backend/app/api/v1/notifications.py` — postback処理追加

**次にやること:**
- [ ] `alembic upgrade head` でマイグレーション適用
- [ ] VPSデプロイ
- [ ] `POST /api/v1/notifications/test` でLINE送信確認
- [ ] LINEでpostbackボタン動作確認

---

## 前回セッション（2026-02-22 第1回）の作業内容

### SP版レスポンシブ対応

**完了:**
- [x] RaceTable: モバイルカードレイアウト（10列テーブル→コンパクトカード、sm:hiddenで切替）
- [x] RaceFilters: 2列グリッドレイアウト（横はみ出し解消）
- [x] RaceCalendar: overflow-hidden追加、モバイルpadding最適化
- [x] PredictionTable: モバイルカードレイアウト + デスクトップ全幅展開行
- [x] Header: ハンバーガーメニュー対応確認済み
- [x] Playwright E2Eテスト: PC/SPスモークテスト19件 + SP横はみ出しテスト5件、全パス
- [x] VPSデプロイ完了

**未完了:**
- [ ] RaceFilters: 日付指定（input[type="date"]）と競馬場（select）の見た目の幅が揃わない

**変更ファイル:**
- `frontend/src/components/RaceTable.tsx` — モバイルカード化
- `frontend/src/components/RaceFilters.tsx` — グリッドレイアウト
- `frontend/src/components/RaceCalendar.tsx` — overflow-hidden
- `frontend/src/components/PredictionTable.tsx` — モバイルカード+全幅展開行
- `frontend/src/app/races/page.tsx` — min-w-0追加
- `frontend/e2e/vps-smoke.spec.ts` — スモークテスト
- `frontend/e2e/sp-overflow.spec.ts` — 横はみ出しテスト
- `frontend/playwright.config.ts` — Playwright設定

---

## 前回セッション（2026-02-21 第3回）の作業内容

### Step C: LINE通知システム実装

**Phase 1: 基盤**
- [x] `pyproject.toml` に `line-bot-sdk>=3.14.0` 追加（3.22.0 インストール済み）
- [x] `config.py` に `LINE_USER_ID` + 通知スケジューラ設定追加
- [x] `notification_log.py` 新規作成（direction, message_type, category, status, payload JSONB）
- [x] `models/__init__.py` に NotificationLog 登録
- [x] Alembicマイグレーション `a1b2c3d4e567` 作成・適用済み

**Phase 2: サービス層**
- [x] `notification_service.py` 全面書き換え → LINE SDK `AsyncMessagingApi` + `AsyncApiClient`
- [x] `push_text` / `push_flex` / `push_prediction_notification` / `push_results_notification` / `push_weekly_report` / `push_test_message`
- [x] 全送信を NotificationLog に記録、LINE未設定時は graceful skip
- [x] `line_templates.py` 新規作成: Flex Message テンプレート4種
  - `build_prediction_flex()` — AI予想サマリー
  - `build_results_flex()` — レース結果サマリー
  - `build_weekly_report_flex()` — 週次レポート
  - `build_interactive_flex()` — 汎用ボタン付き（Step 5/6 の土台）

**Phase 3: APIエンドポイント**
- [x] `notifications.py` 全面書き換え
  - `POST /webhook` — LINE Webhook受信（WebhookParser + 署名検証）
  - `POST /test` — テスト通知送信
  - `GET /logs` — 通知ログ一覧（ページネーション付き）
- [x] `schemas/notification.py` 新規作成

**Phase 4: スケジューラ連携**
- [x] `jobs.py` に `job_notify_prediction`（毎日 19:00 JST）追加
- [x] `jobs.py` に `job_notify_results`（毎日 20:00 JST）追加
- [x] `register_jobs` で計7ジョブ登録

**Phase 5: 動作確認**
- [x] `uv sync` — 依存関係インストール成功
- [x] `alembic upgrade head` — マイグレーション適用成功
- [x] LINE SDK インポート確認 OK
- [x] テンプレート生成 + FlexContainer.from_dict() 変換 OK

### 次にやること（LINE Developer Console セットアップ）
- [ ] https://developers.line.biz/ でチャネル作成
- [ ] Channel Secret / Channel Access Token を取得
- [ ] `.env` に `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID` を設定
- [ ] サーバー再起動後 `POST /api/v1/notifications/test` でテスト通知確認
- [ ] ngrok で Webhook URL を公開し、LINE Developer Console に設定
- [ ] PostbackEvent 受信の動作確認

---

## 完了済みステップ

- [x] **Step 1:** データ取得・保存の自動化（CSV取り込み、FastAPI、PostgreSQL）
- [x] **Step 2:** 予想 → 照合 → 記録の自動化（LightGBM、SHAP、17テスト通過）
- [x] **Step 3:** ダッシュボード・グラフの自動更新（Next.js 15、ダークモードUI）

## 現在のステップ: リアルタイムデータ取得（Step 3.5）

### 決定事項（2026-02-20）

1. **方式C（ハイブリッド）を採用**
   - 普段: クラウドで netkeiba + Yahoo!競馬 スクレイピング（無料・自動）
   - 週1回: 自宅PCで JRA-VAN データ同期（月2,090円・手動コマンド1回）

2. **JRA-VAN連携は後回し**
   - 開発中・フェーズ1序盤はスクレイピングのみで進める
   - 実運用3ヶ月後を目安にJRA-VAN追加（止まると困る段階になってから）

3. **LINE通知でJRA-VAN同期リマインダー**
   - 週1回「同期してください」通知 → コマンド実行 → 完了通知
   - Step 4（LINE通知）と一緒に実装

### 実装順序

```
Step A: netkeiba スクレイピング構築               ✅ 完了
Step B: フロントエンド機能大幅拡張（13機能+馬画像）     ✅ 完了
Step C: LINE通知システム（方針書のStep 4）            ✅ コード実装完了（要: LINE Console設定）
Step D: JRA-VAN連携追加（3ヶ月後目安）
Step E: LINEでJRA-VAN同期リマインダー通知
```

### Step A の実装状況（2026-02-20 完了）

- [x] 依存パッケージ追加（playwright, beautifulsoup4, lxml）
- [x] 新DBモデル作成（OddsSnapshot, ScrapeLog）
- [x] 既存モデル拡張（Race/RaceEntry に data_source、Horse に netkeiba_id）
- [x] Alembicマイグレーション作成
- [x] パーサー実装（race_list, shutuba, odds, result）— 8テスト通過
- [x] BaseScraper（Playwright管理、レート制限3-10秒、リトライ3回）
- [x] NetkeibaScraper（出馬表・オッズAPI・結果取得）
- [x] store.py（DB保存: upsertパターン、ScrapeLog記録）
- [x] CLIコマンド追加（scrape shutuba/odds/result --date）
- [x] Makefileターゲット追加（scrape-shutuba/odds/result, playwright-install）
- [ ] **次に必要:** Docker起動 → `make db-upgrade` → `make playwright-install` → 手動E2Eテスト
- [ ] Yahoo!競馬バックアップスクレイパー（後日追加）

**新規ファイル一覧:**
```
backend/app/scraper/__init__.py
backend/app/scraper/base.py
backend/app/scraper/netkeiba.py
backend/app/scraper/store.py
backend/app/scraper/parsers/__init__.py
backend/app/scraper/parsers/race_list.py
backend/app/scraper/parsers/shutuba.py
backend/app/scraper/parsers/odds.py
backend/app/scraper/parsers/result.py
backend/app/models/odds_snapshot.py
backend/app/models/scrape_log.py
backend/tests/scraper/test_parsers.py
```

### Step B の実装状況（2026-02-20 完了）

**Phase 1: レース探索UX改善 (A1-A4)**
- [x] 月・週単位フィルター（year_month/weekクエリパラメータ）
- [x] レースカレンダー（7列ミニカレンダー、日クリックでフィルタ）
- [x] 出馬表ページ（未来レースisUpcoming対応、枠番順ソート）
- [x] 馬場・コンディション表示（CourseInfoBadgesコンポーネント）

**Phase 2: 馬詳細ページ + 画像 (A5)**
- [x] 馬詳細API（`GET /horses/{horse_id}` + 過去成績・勝率・馬場別成績）
- [x] 馬詳細ページ（画像+成績サマリー+馬場別バー+レース履歴）
- [x] 馬名リンク化（EntryTable, PredictionTableから `/horses/{id}` へ）
- [x] netkeiba CDN画像 + フォールバックSVG

**Phase 3: リアルタイムオッズ + グラフ (B1, B2)**
- [x] 最新オッズAPI（`GET /races/{race_id}/odds`）
- [x] オッズ更新API（`POST /races/{race_id}/odds/refresh`）
- [x] オッズ変動履歴API（`GET /races/{race_id}/odds/history`）
- [x] SVG折れ線グラフ（OddsChart、枠色カラーリング）

**Phase 4: AI分析強化 (C1, C2, C3)**
- [x] SHAP視覚化（横棒グラフ、日本語ラベル）
- [x] 荒れ度バッジ（UpsetBadge: 荒/普通/本命）
- [x] コース適性分析（★1-3表示、同馬場・同距離帯±200m）
- [x] prediction_logs.shap_data (JSONB) マイグレーション

**Phase 5: シミュレーション + 収支管理 (D1, D2)**
- [x] 馬券シミュレーター（単勝/複勝、JRA方式払戻計算）
- [x] 収支管理API（CRUD + 集計: `POST/GET/PUT /bets`, `GET /bets/summary`）
- [x] 収支管理ページ（サマリーカード+履歴テーブル+結果入力）
- [x] bet_recordsテーブルマイグレーション

**Phase 6: LINE通知スタブ (E4)**
- [x] notification_service.py（スタブクラス）
- [x] notifications.py（テストエンドポイント）
- [x] config.pyにLINE設定項目追加

**新規ファイル一覧（Backend）:**
```
backend/app/api/v1/calendar.py
backend/app/api/v1/horses.py
backend/app/api/v1/bets.py
backend/app/api/v1/notifications.py
backend/app/services/calendar_service.py
backend/app/services/horse_service.py
backend/app/services/bet_service.py
backend/app/services/notification_service.py
backend/app/schemas/calendar.py
backend/app/schemas/horse.py
backend/app/schemas/bet.py
backend/app/models/bet_record.py
backend/alembic/versions/b5d9f12e6789_add_horse_image_url.py
backend/alembic/versions/c6e0a23b4567_add_shap_data.py
backend/alembic/versions/d7f1b34c5678_create_bet_records.py
```

**新規ファイル一覧（Frontend）:**
```
frontend/src/components/RaceCalendar.tsx
frontend/src/components/CourseInfoBadges.tsx
frontend/src/components/OddsChart.tsx
frontend/src/components/ShapChart.tsx
frontend/src/components/UpsetBadge.tsx
frontend/src/components/AptitudeIndicator.tsx
frontend/src/components/BettingSimulator.tsx
frontend/src/components/BetSummaryCard.tsx
frontend/src/app/horses/[horseId]/page.tsx
frontend/src/app/bets/page.tsx
```

- [ ] **次に必要:** Docker起動 → `make db-upgrade`（3マイグレーション適用） → ブラウザ手動確認

### 未着手ステップ

- [x] **Step 4:** LINE通知システムの構築（コード実装完了、要LINE Console設定）
- [x] **Step 5:** 自動レポート・改善提案（週次レポート・ハズレ原因確認・月次改善提案）
- [~] **Step 6:** モデル自動再学習・切り替え（MLOps）← **現在ここ**。v1.1.0手動再学習は完了、自動化は未着手

---

## 参照ファイル

- 総合方針書: `C:\Users\unoen\Downloads\競馬AI予想アプリ_総合方針まとめ_2.md`
- Step 2 実装記録: `docs/20260219-step2-implementation.md`
- CHANGELOG: `CHANGELOG.md`

## 既存のデータ状況

- Kaggle CSV: 1986〜2021年の過去データ（DB投入済み）
- 学習済みモデル: `backend/models/v1.0.0.joblib` + `v1.1.0.joblib`（特徴量6つ追加版）
- リアルタイムデータ: netkeiba スクレイパー本番稼働中（スケジューラ自動化済み）
- 馬券シミュレーター: 実装済み（単複＋ボックス・フォーメーション・流し）
- 本番環境: VPS稼働中。E2Eヘルスチェックで日々の本番状態を検証
