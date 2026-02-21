# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **AI予想成績ページ** (`/results`) — AI予想と実結果の比較・的中率分析
  - カレンダーUIで日付選択、競馬場タブでフィルタリング
  - 7馬券種（単勝/複勝/馬連/馬単/ワイド/3連複/3連単）の的中率サマリーカード
  - レース結果一覧（結果TOP3 / AI予想TOP3 / 的中バッジ表示）
  - 初回表示時に最新結果日に自動ジャンプ
  - Backend: `results_service.py` (的中判定ロジック), `api/v1/results.py` (5エンドポイント)
- **スケジューラ管理** — APScheduler によるデータ収集自動化
  - 5ジョブ: カレンダー(6:00), 出馬表(18:00), AI予想(18:30), オッズ(8-16:30/30分毎), 結果(17:00,19:00)
  - SchedulerStatus ダッシュボードウィジェット（手動実行・一時停止・再開ボタン）
  - REST API: ステータス確認/手動トリガー/一時停止/再開
  - 全スケジュール設定を環境変数で変更可能
- **AI予想自動化** — 出馬表取得後に翌日レースのAI予想を自動実行
  - `job_predict`: 毎日18:30 JST (出馬表取得30分後)
  - モデルバージョンは `SCHED_PREDICT_MODEL_VERSION` 環境変数で設定可能

### Fixed
- Next.js 15.5 ビルドエラー修正（`not-found.tsx` 追加）
- AiRecommendations.tsx 複勝の picks 値修正 (3→1)

- **馬券シミュレーション拡張** — 7馬券種対応＋専用ページ新設
  - BettingSimulator: 単勝・複勝・馬連・馬単・ワイド・三連複・三連単の7種対応
  - 馬券種に応じた動的UI（1〜3頭選択、馬単/三連単は着順ラベル付き）
  - 単勝のみオッズ自動取得、他は手入力方式
  - `/races/[raceId]/simulate` シミュレーション専用ページ新設（2カラムレイアウト）
  - オッズテーブル＋変動グラフを左カラムに配置、シミュレーターを右カラムに配置
  - セッション内記録一覧（合計金額表示付き）
  - レース詳細ページの埋め込みSimulatorをリンクボタンに変更（視認性改善）
- **Step A: netkeiba スクレイピング** — Playwright + BeautifulSoup4 によるスクレイパー
  - パーサー（race_list, shutuba, odds, result）、8テスト通過
  - BaseScraper（Playwright管理、レート制限3-10秒、リトライ3回）
  - NetkeibaScraper（出馬表・オッズ・結果取得）
  - DB保存（upsertパターン、ScrapeLog記録）
  - CLIコマンド追加（scrape shutuba/odds/result --date）
  - 新モデル: OddsSnapshot, ScrapeLog
- **Step B: フロントエンド機能大幅拡張（13機能 + 馬画像）**
  - Phase 1: レース探索UX — 月/週フィルタ、レースカレンダー（月移動対応）、出馬表（未来レース対応）、馬場バッジ
  - Phase 2: 馬詳細ページ — 馬画像（netkeiba CDN + フォールバックSVG）、成績サマリー、馬場別成績バー、過去レース一覧
  - Phase 3: リアルタイムオッズ — 最新オッズAPI、オッズ更新、純SVG折れ線グラフ（枠色カラーリング）
  - Phase 4: AI分析強化 — SHAP横棒グラフ（日本語ラベル）、荒れ度バッジ、コース適性★1-3表示
  - Phase 5: シミュレーション+収支管理 — 馬券シミュレーター（JRA方式払戻計算）、収支CRUD API、収支管理ページ
  - Phase 6: LINE通知スタブ — notification_service/API スタブ、config設定項目
  - race_idから競馬場名をデコードするフォールバック表示

### Fixed
- bets APIルート順序修正（`GET /summary` が `PUT /{bet_id}` より先に定義されるよう変更）
- レースカレンダーのデフォルト月をデータ最新月に変更（データなし月で全日disabled問題を解消）
- カレンダーをモバイルでも表示するよう変更

### Changed
- DBマイグレーション3件追加: horses.image_url, prediction_logs.shap_data(JSONB), bet_recordsテーブル

---

- **Step 1: Data Pipeline + API** — CSV取り込みパイプライン、FastAPI REST API（7エンドポイント）、PostgreSQL 16 + SQLAlchemy 2.0 async
- **Step 2: ML Prediction Pipeline** — LightGBM予測モデル、SHAP説明、モデルバージョン管理、予測ログ保存、17テスト通過
- **Step 3: Frontend** — Next.js 15 + React 19 + Tailwind CSS 4 フロントエンド
  - ダッシュボード（データ概要 + モデル性能 + 使い方ガイド）
  - レース一覧（日付/競馬場フィルタ + ページネーション + テーブル見方ガイド）
  - レース詳細 + AI予測（SHAP説明、信頼度バッジ、プログレスバー、枠番カラー）
  - モデル管理（展開式メトリクスカード）
  - ダークモードUIリデザイン（Noto Sans JP、グラスモーフィズムカード、アクセントグロー）
  - API rewrite プロキシ（CORS回避）
