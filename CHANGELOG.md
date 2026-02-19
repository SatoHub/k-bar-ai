# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Step 1: Data Pipeline + API** — CSV取り込みパイプライン、FastAPI REST API（7エンドポイント）、PostgreSQL 16 + SQLAlchemy 2.0 async
- **Step 2: ML Prediction Pipeline** — LightGBM予測モデル、SHAP説明、モデルバージョン管理、予測ログ保存、17テスト通過
- **Step 3: Frontend** — Next.js 15 + React 19 + Tailwind CSS 4 フロントエンド
  - ダッシュボード（データ概要 + モデル性能 + 使い方ガイド）
  - レース一覧（日付/競馬場フィルタ + ページネーション + テーブル見方ガイド）
  - レース詳細 + AI予測（SHAP説明、信頼度バッジ、プログレスバー、枠番カラー）
  - モデル管理（展開式メトリクスカード）
  - ダークモードUIリデザイン（Noto Sans JP、グラスモーフィズムカード、アクセントグロー）
  - API rewrite プロキシ（CORS回避）
