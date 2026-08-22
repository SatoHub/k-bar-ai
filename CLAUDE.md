# K-Bar AI — プロジェクト指示

## セッション開始時の自動起動

**毎回セッション開始時に、以下を自動実行すること:**

```bash
# 1. Docker (PostgreSQL) 起動
docker compose -f docker/docker-compose.yml --env-file .env up -d

# 2. DBマイグレーション適用
cd backend && uv run alembic upgrade head

# 3. バックエンドAPI起動 (バックグラウンド)
# ⚠️ --reload は使わない（scheduler 起動が重く、孤立ワーカーがポート8000を掴む事故が起きる）
cd backend && uv run uvicorn app.main:app --port 8000 &

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

## 検証コマンド（変更後に必ず実行する）

⚠️ **`make` はこの Windows 環境に未インストール**。上表の `make xxx` は動かないため、
実際に検証する時は以下の実コマンドを使うこと（すべて動作確認済み）。

| 用途 | コマンド |
|---|---|
| backend テスト | `cd backend && uv run pytest -q` |
| backend lint | `cd backend && uv run ruff check .` |
| backend format | `cd backend && uv run ruff format .` |
| frontend 型チェック | `cd frontend && npm run typecheck` |
| frontend lint | `cd frontend && npm run lint` |
| frontend ビルド | `cd frontend && npm run build` |
| 本番ヘルスチェック | `cd frontend && npx playwright test e2e/production-health-check.spec.ts --project=PC --reporter=list` |

- `tests/test_health.py` は **PostgreSQL が必要**（Docker 起動が前提）。Docker が落ちていると
  3件が ConnectionRefused で失敗する。これは環境要因であり、コードの不具合ではない。
- 実行できなかった検証があれば、**隠さず報告すること**。

## 自動チェック（hook・.claude/hooks/）

ファイル編集のたびに自動実行される。設定は `.claude/hooks/checks.json`。

| 編集対象 | 自動実行される内容 |
|---|---|
| `backend/{app,scripts,tests}/**.py` | `ruff format` → `ruff check --fix` → 対応する `tests/test_<名前>.py` |
| `frontend/{src,e2e}/**.{ts,tsx}` | `npx tsc --noEmit --incremental false`（約4秒） |

`--incremental false` は必須。付けないと追跡対象の `tsconfig.tsbuildinfo` を毎回書き換え、
変更と無関係な差分が残り続ける。

- 成功時は無言。失敗時だけ結果が Claude に渡される。
- **重い検証（全テスト・build・E2E）は hook 化していない。** タスク完了時に上表のコマンドで自分で実行する。

## ユーザーの承認が必要な操作（hook が機械的にブロック）

`.claude/hooks/guard.json` に定義。**Bash / PowerShell の両ツール**に適用される。
承認された場合のみコマンド末尾に ` #APPROVED-BY-USER` を付けて再実行する。
**ユーザーが承認していないのにマーカーを付けること、別ツールに切り替えて回避することは禁止。**

git 破壊的操作（`git -C` 付きも）/ force push / 履歴書き換え / ssh・scp・rsync /
外部への更新系 curl・Invoke-RestMethod（`-X` 無しの `--data` 等も）/
`docker-compose.prod.yml` 操作 / VPS へのDB同期 / 認証情報変更 / DB破壊操作 /
依存パッケージ追加 / 広範囲の再帰削除（`rm -rf ./*` や `Remove-Item -Recurse` も）

ルールを変えたら回帰テストを回すこと（ブロック漏れと誤検知の両方を検査する）:

```bash
node .claude/hooks/guard.test.mjs
```

⚠️ **master への push は GitHub Actions 経由で本番VPSへ自動デプロイされる。**
push はユーザーが明示的に指示した時だけ行うこと。

## 追加レビューを回すパス（このリポジトリ固有）

通常の変更は Claude の `code-reviewer` のみ（Medium 以上で自動・1〜2分）。
**以下のパスに触れたら、差分が1行でも**追加のレビュアーを回す。
判定表の全体は `~/.claude/CLAUDE.md` §12.3。

| カテゴリ | 該当パス | 追加で回すもの |
|---|---|---|
| **金銭に関わる計算** | `backend/app/services/bet_suggestion*.py`、`hedge_service.py`、`bet_service.py`、`backend/app/ml/` | `security-reviewer` ＋ `codex` |
| 認証・外部公開 | `backend/app/api/` の認証まわり、`docker/nginx/`、`.htpasswd` 関連 | `security-reviewer` ＋ `codex` |
| 外部入力・スクレイピング | `backend/app/scraper/` | `security-reviewer` |
| DBスキーマ | `backend/alembic/versions/`、`backend/app/models/` | `security-reviewer` ＋ `codex` |
| 本番・デプロイ | `.github/workflows/`、`docker/docker-compose.prod.yml`、`backend/app/scheduler/` | `codex` |
| 安全機構 | `.claude/hooks/`、`.claude/settings.json` | `codex` |
| テストを触った時 | `backend/tests/`、`frontend/e2e/` | `test-reviewer` |

- 金銭計算を `security-reviewer` に含めるのは、**計算ミスがそのまま金銭損失になる**ため。
- `codex` は約9分かかるので**バックグラウンド実行**する。起動オプションは `~/.claude/CLAUDE.md` §12.10
  （`-c` 2つを省くと**別コミットをレビューして誤った合格を返す**）。
- 完了報告に `レビュー: code-reviewer=... / test-reviewer=... / security-reviewer=...` の
  1行を**必ず**含める。

## Project Rules

- **機密情報を絶対にコミットしない。** このリポジトリは public。秘匿値は `.env` / `frontend/.env.local`（共に gitignore）へ。
- ローカルの uvicorn は `--reload` を使わない（scheduler 起動が重く、孤立ワーカーがポート8000を掴む事故が起きる）。
  `cd backend && uv run uvicorn app.main:app --port 8000`
- スクレイピングは間隔 3〜10秒ランダム（netkeiba / JRA公式への負荷配慮）。
- backend は ruff で整形・lint 済み（clean 状態を維持する）。
- 学んだことは `docs/YYYYMMDD-トピック.md` に記録。大規模・高リスク変更の仕様書は `docs/specs/` に置く。
- 既知バグは `docs/20260228-bug-registry.md`、進捗は `docs/progress.md`。
