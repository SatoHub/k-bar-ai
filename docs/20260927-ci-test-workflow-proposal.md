# CI でテストを走らせる workflow の差分案（未適用）

作成日: 2026-09-27

## なぜ必要か

**現状 `.github/workflows/` には `deploy.yml` しか無く、CI でテストが一度も走っていない。**
つまり `master` に push した内容は、テストが落ちていてもそのまま本番にデプロイされる。

2026-09-27 に発覚した特徴量のバグ（`rolling`/`expanding` を groupby の外で呼び、
24特徴量が別エンティティの値を拾っていた）は、
`backend/tests/test_features.py` に回帰テストを追加して塞いだ。
ただし**このテストを強制する仕組みが CI に無い**ため、次に誰かが壊しても気づけない。

- ローカルの post-edit hook（`.claude/hooks/checks.json`）は
  `backend/app/ml/features.py` を編集すると `tests/test_features.py` を自動実行する
  （`namePattern: "test_{base}"` により `features` → `test_features` に解決される）。
  **Claude Code 経由の編集は守られているが、手で編集した場合や CI は守られていない。**

## ⚠️ 適用にはユーザー対応が必要

`.github/workflows/` への push には **`workflow` スコープ付きトークンが必要**。
ローカルの既定トークンは `repo` のみなので push が拒否される
（経緯は `~/.claude/CLAUDE.md` および memory の `vps-deploy` 参照）。
そのため**この差分は適用せず案として残す**。

## 差分案

新規ファイル `.github/workflows/test.yml`:

```yaml
name: Test

on:
  push:
    branches: [master]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Install deps
        working-directory: backend
        run: uv sync --frozen
      - name: Lint
        working-directory: backend
        run: uv run ruff check .
      # ⚠️ tests/test_health.py は PostgreSQL が必要（CLAUDE.md に明記）。
      #    CI に DB を立てるまでは除外する。--deselect ではなく
      #    --ignore でファイル単位に外すこと（個別に増えても壊れない）。
      - name: Test (DB 不要のもの)
        working-directory: backend
        run: uv run pytest tests/ -q --ignore=tests/test_health.py

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install deps
        working-directory: frontend
        run: npm ci
      - name: Typecheck
        working-directory: frontend
        run: npm run typecheck
      - name: Lint
        working-directory: frontend
        run: npm run lint
```

## 次の段階（この案には含めていない）

1. **`deploy.yml` をテスト成功に依存させる。** `needs: [backend, frontend]` を足すか、
   `workflow_run` で連鎖させる。現状はテストと無関係にデプロイが走る
2. **CI に PostgreSQL サービスを足して `test_health.py` も回す。**
   `services: postgres:16-alpine` + マイグレーション適用が必要
3. **`deploy.yml` が `deploy/deploy.sh` を呼ばない問題**（別の既知課題。
   `docs/20260916-https-ip-certificate.md` の残課題2）も同時に直すのが望ましい
