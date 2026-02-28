# K-Bar AI — プロジェクト指示

## セッション開始時の自動起動

**毎回セッション開始時に、以下を自動実行すること:**

```bash
# 1. Docker (PostgreSQL) 起動
docker compose -f docker/docker-compose.yml --env-file .env up -d

# 2. DBマイグレーション適用
cd backend && uv run alembic upgrade head

# 3. バックエンドAPI起動 (バックグラウンド)
cd backend && uv run uvicorn app.main:app --reload --port 8000 &

# 4. フロントエンド起動 (バックグラウンド)
cd frontend && npm run dev &
```

起動後、以下を順に実行すること:

1. **本番環境ヘルスチェック** — Playwrightで本番VPSのデータ・UI状態を自動検証する
```bash
cd frontend && npx playwright test e2e/production-health-check.spec.ts --project=PC --reporter=list
```
- テスト結果をユーザーに要約して報告すること（全パス / 失敗テストの一覧）
- 失敗がある場合は `docs/20260228-bug-registry.md` と照合し、既知バグの再発か新規バグかを判断する
- スクリーンショットは `frontend/e2e/screenshots/health-*.png` に保存される

2. `docs/progress.md` を確認して前回の作業状況を把握すること

## プロジェクト構成

- Backend: `backend/` — FastAPI + PostgreSQL + SQLAlchemy async + LightGBM
- Frontend: `frontend/` — Next.js 15 + React 19 + Tailwind CSS 4
- Docker: `docker/docker-compose.yml` — PostgreSQL 16 + pgAdmin
- ML Models: `backend/models/` — LightGBM (.joblib)

## 重要なコマンド

| コマンド | 説明 |
|---------|------|
| `make dev-all` | Docker + API + Frontend を一括起動 |
| `make scrape-shutuba date=YYYY-MM-DD` | 出馬表スクレイピング |
| `make scrape-odds date=YYYY-MM-DD` | オッズスクレイピング |
| `make predict version=v1.0.0 date=YYYY-MM-DD` | AI予想実行 |
| `make test` | バックエンドテスト |
| `cd frontend && npx playwright test e2e/production-health-check.spec.ts --project=PC` | 本番ヘルスチェック |
