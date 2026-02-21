# 競馬AI予想アプリ 進捗管理

**最終更新:** 2026-02-21（AI推奨・競馬場タブ・発走時刻表示 追加）

---

## 前回セッション（2026-02-21 第2回）の作業内容

### AI推奨ベット表示（シミュレーションページ）
- [x] AiRecommendations.tsx 新規作成: 7馬券種ごとのAI推奨表示
- [x] ◎○▲△☆ランクマーク、スコアバー、信頼度バッジ
- [x] クリックでBettingSimulatorに自動入力（prefill機構）
- [x] simulate/page.tsx にAI予想データ取得・prefill連携追加

### 競馬場タブフィルター（レース一覧）
- [x] races/page.tsx: 東京/阪神/小倉タブ表示（日付選択時のみ）
- [x] decodeRacecourse() によるクライアントサイドフィルタリング
- [x] 各タブにレース数バッジ表示
- [x] per_page=50 で日付指定時の全件取得対応

### 発走時刻・レース状態表示
- [x] Race モデルに post_time (Time) カラム追加 + マイグレーション
- [x] RaceTable.tsx: 発走時刻列 + ステータスバッジ（終了/発走中/未発走）
- [x] 終了レースは半透明表示、発走中はアニメーション付きドット
- [x] scraper/store.py: post_time の保存対応（_parse_post_time ヘルパー）
- [x] cli.py: race_listからshutuba dataへpost_time マージ

### データ取得（2/21・2/22）
- [x] 2/21(土) 出馬表: 36レース、530頭
- [x] 2/21(土) オッズ: 242件取得
- [x] 2/21(土) AI予想: 530頭分
- [x] 2/22(日) 出馬表: 36レース、497頭（前回セッションで取得済み）
- [x] 2/22(日) AI予想: 497頭分（前回セッションで取得済み）
- [ ] 2/22(日) オッズ: 未配信のため未取得

### バグ修正
- [x] React key重複エラー（ワイド推奨のkey修正）
- [x] uvicorn/nodeゾンビプロセスによるAPIキャッシュ問題解消
- [x] ENOENT `.next/server/app/races/page.js` エラー修正

### 未対応・次回やること
- [ ] 2/22 オッズ取得（朝以降にnetkeiba配信開始後）
- [ ] 複数回オッズ取得でオッズ変動グラフ動作確認
- [ ] racecourse_name / race_name が null の問題（shutubaパーサーCSS selector修正）
- [ ] weatherの末尾スラッシュ除去（"晴/" → "晴"）
- [ ] 予想精度: 現モデルは2021年以前データで学習済み。最新データでの再学習は将来課題
- [ ] Step C: LINE通知システム（方針書のStep 4）

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
Step C: LINE通知システム（方針書のStep 4）            ← 次にやる
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

- [ ] **Step 4:** LINE通知システムの構築
- [ ] **Step 5:** 自動レポート生成（週次・月次・3ヶ月次）
- [ ] **Step 6:** モデル自動再学習・切り替え（MLOps）

---

## 参照ファイル

- 総合方針書: `C:\Users\unoen\Downloads\競馬AI予想アプリ_総合方針まとめ_2.md`
- Step 2 実装記録: `docs/20260219-step2-implementation.md`
- CHANGELOG: `CHANGELOG.md`

## 既存のデータ状況

- Kaggle CSV: 1986〜2021年の過去データ（DB投入済み）
- 学習済みモデル: `backend/models/v1.0.0.joblib`（LightGBM）
- リアルタイムデータ: netkeiba スクレイパー実装済み（要 DB upgrade + E2Eテスト）
- 馬券シミュレーター: 未実装
