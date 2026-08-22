# AI開発標準セットアップ（2026-08-22）

Claude Code を「コードを書く道具」から「調査→計画→実装→検証→レビューまで回す開発エージェント」に
変えるための永続設定。**ユーザーがこの手順を忘れても Claude 側が自動で再現する**ことが目的。

---

## 1. 設計の考え方 — なぜ3層に分けたか

ルールを全部 CLAUDE.md に書くと、毎セッション全文がコンテキストに載って**トークンを食い続ける**。
そこで「いつ必要か」で3層に分離した。

| 層 | 実体 | 読み込まれるタイミング | 入れたもの |
|---|---|---|---|
| **常時** | `CLAUDE.md` | 毎セッション必ず | 規模判定と発動条件（短く） |
| **必要時** | Skills / Subagents | 該当タスクの時だけ | 手順の詳細・レビュー観点 |
| **機械的** | Hooks | ファイル編集・コマンド実行のたび | format / typecheck / テスト / 危険操作ブロック |

判断を要さない機械的な処理（整形・型チェック・破壊的操作の阻止）は、Claude の判断に任せず
**Hook に落とした**。Claude が忘れても実行されるため。

---

## 2. Global（`~/.claude/` — 全プロジェクトで有効）

### 2.1 Subagents（独立した文脈で動く専門家）

`~/.claude/agents/*.md`

| 名前 | 役割 | 起動条件 |
|---|---|---|
| `code-reviewer` | 実装者の説明を信用せず、実際の diff と関連コードだけで欠陥を探す。Critical/High/Medium/Low で報告 | Medium 以上の変更後（自動） |
| `test-reviewer` | テストの抜け・偽陽性（何も検証していないテスト）・失敗系の欠落を検出 | テストを書いた/変えた時 |
| `security-reviewer` | 攻撃者視点で認証・認可・入力・シークレットを検査 | High Risk 変更のみ |
| `researcher` | 実装せず調査だけして要約を返す | 読むファイルが5つを超える時 |

**なぜ分離するか**: 実装した本人（メインの Claude）は自分のコードを肯定しやすい。
別コンテキストのレビュアーには「実装は正しい」という前提を渡さないため、
説明とコードが食い違えば**コードを正**として判定する。

**なぜ researcher が要るか**: 大量ファイルを読むとメインの文脈が汚れて後半の精度が落ちる。
調査は別コンテキストにやらせ、要約だけ受け取る。

### 2.2 Skills（必要時だけ読まれる手順書）

`~/.claude/skills/*/SKILL.md`

| 名前 | 中身 |
|---|---|
| `feature-development` | 調査 → 要件確定 → 計画 → 小分割 → 実装 → 検証 → 独立レビュー → ドキュメント → 報告 |
| `bug-fix` | 再現 → 根本原因 → **回帰テストを先に書く** → 最小限の修正 → 検証 → レビュー |
| `specification` | 大規模/高リスク変更の仕様書テンプレ（受け入れ条件・エラーケース・ロールバック） |
| `setup-ai-development` | **新規リポジトリ用インストーラ**（後述） |

既存の `tdd` / `diagnosing-bugs` / 組み込み `/code-review` とは**役割を重複させず、それらを呼ぶ**構成。

### 2.3 CLAUDE.md §12（常時ロード・短く保つ）

規模判定と自動発動ルールだけを置いた。全311行（上限500行）。既存の1〜11節は無変更。

| 規模 | 例 | 流れ |
|---|---|---|
| **Small** | typo・CSS微修正・明白な1行バグ | 調査 → 実装 → 関連チェック |
| **Medium** | API追加・UI機能・バグ修正・DBクエリ変更 | ＋計画・テスト・**独立レビュー** |
| **Large/HighRisk** | 認証・課金・マイグレーション・アーキ変更 | ＋**仕様書**・セキュリティレビュー・全体検証 |

**全タスクを重量級にしない**のが要点。Small に計画書もレビュアーも起動しない（コスト対策）。

### 2.4 Global Installer

新しいリポジトリで一言:

```
このRepositoryをAI開発標準にセットアップして
```

→ `setup-ai-development` が起動し、対象リポジトリを実際に調査して
（package.json / Makefile / pyproject.toml 等から**実在するコマンドだけ**を拾い）、
そのスタックに合わせた CLAUDE.md・hooks を生成する。技術スタックはスキルにハードコードしていない。

同梱物:
- `templates/post-edit.mjs` / `guard-command.mjs` / `guard.test.mjs` — 設定ファイル駆動の汎用 hook と回帰テスト雛形
- `reference/hooks-schema.md` — 公式ドキュメントで**確認済み**の hooks/agents/skills 仕様

---

## 3. Project（k-bar-ai だけ）

### 3.1 編集時の自動チェック（`.claude/hooks/checks.json`）

| 編集対象 | 自動実行 | 実測 |
|---|---|---|
| `backend/{app,scripts,tests}/**.py` | `ruff format` → `ruff check --fix` → 対応する `tests/test_<名前>.py` | 3.5秒（DB不要テスト） |
| `frontend/{src,e2e}/**.{ts,tsx}` | `npx tsc --noEmit --incremental false` | 約4秒 |

- 成功時は**無言**。失敗時だけ結果が Claude に渡る。
- 関連テストは**実在する時だけ**走る（`app/api/v1/health.py` → `tests/test_health.py` を自動発見）。
- 重い検証（全テスト・build・E2E）は hook 化していない。開発速度を殺さないため。

### 3.2 危険コマンドの機械的ブロック（`.claude/hooks/guard.json`）

**Bash / PowerShell の両ツール**に適用される。

ブロック対象: git破壊的操作（`git -C` 付きも）/ force push / 履歴書き換え / ssh・scp・rsync /
外部への更新系 curl・Invoke-RestMethod（`-X` 無しの `--data` 等も）/ 本番 compose ファイル操作 /
VPS へのDB同期 / 認証情報変更 / DB破壊 / **依存パッケージ追加** /
広範な再帰削除（`rm -rf ./*` や `Remove-Item -Recurse` も）

通す: `git status` / `git -C <path> status` / `git push`(通常) / GET curl / localhost への POST /
ローカル docker / `alembic upgrade` / 引数なし `npm install` / `rm -rf node_modules` —
**`guard.test.mjs` の53ケースで pass**（ブロック漏れ・誤検知とも0）

承認された時だけコマンド末尾に ` #APPROVED-BY-USER` を付けて再実行する。

> ⚠️ このマーカーは Claude 自身が付けられる＝**技術的な強制力ではなく速度制限**。
> 「確認せずに本番を触る」事故を防ぐためのもので、悪意ある回避は防げない。

> ⚠️ **公開リポジトリなので guard.json に本番IPは書いていない**（`ssh` 全般・
> localhost 以外への更新系 curl という汎用パターンで表現）。

### 3.3 その他

- `CLAUDE.md` に**実際に動く検証コマンド表**を追記（`make` はこの環境に未インストールのため）
- `frontend/package.json` に `typecheck` スクリプト追加
- `backend/pyproject.toml` に `testpaths` 追加
- `docs/specs/` 新設

---

## 4. 何が変わったか

| | Before | After |
|---|---|---|
| 依頼の仕方 | 工程ごとにコマンドを覚えて指定 | 「〜して」だけ。規模判定は Claude 側 |
| レビュー | 自分で `/code-review` を思い出す | Medium 以上で自動起動（別コンテキスト） |
| 整形・型チェック | 忘れる／後でまとめて | 編集のたびに自動 |
| 本番事故 | 注意力頼み | hook が止めて確認を強制 |
| 「動いた」の扱い | 完了 | 要件充足＋テスト＋lint/型＋レビューで完了 |
| 検証漏れ | 黙って進む | 実行できなかった検証を明示報告 |

### 副次的に直った既存の不具合

1. `npx tsc --noEmit` が失敗していた（e2e の無効な型指定）→ 修正
2. `uv run pytest` が収集エラーで起動不能（gitignore 済み外部clone を拾っていた）→ `testpaths` 設定
3. `ruff` が 47ファイル未整形＋lint 12件 → 一括整形（commit `538c007`、pytest 37 passed）
4. `make` が未インストールと判明 → CLAUDE.md の記載が実態と乖離していた

---

## 5. 利点

- **忘れても品質が落ちない** — 手順が記憶ではなく設定に載っている
- **コンテキスト効率** — 詳細は必要時だけロード。調査は別エージェント
- **コストは規模連動** — Small では余計なエージェントを起動しない
- **自分のコードを自分で承認しない** — 独立レビューが構造的に入る
- **本番事故のガード** — 判断ミスではなく機構で止める
- **横展開できる** — 新規リポジトリは一言でセットアップ

---

## 6. 限界・注意

- 承認マーカーは**強制力ではない**（3.2 参照）
- 独立レビューは**トークンを消費する**。Small では起動しない設計で緩和済み
- Hook は編集のたびに走る。frontend の tsc は約4秒、backend の関連テストは3〜12秒
- `tests/test_health.py` は **PostgreSQL 必須**。Docker 停止中は3件失敗する（環境要因）
- Subagents・Hooks とも**再起動なしで反映された**（guard が同一セッション内で実際にブロックした）
- **guard はコマンド文字列を正規表現で見るだけ**なので、危険コマンドについて*書いている*だけの
  シェル実行（ドキュメント生成など）も誤検知する。ファイル編集は Bash heredoc ではなく
  Edit / Write ツールを使えば起きない

---

## 7. クロスモデルレビュー（codex）の導入 — 2026-08-22 追記

### なぜ追加したか

`code-reviewer` サブエージェントは**別コンテキストだが同じモデル**。文脈の汚染は防げるが、
**同じモデルは同じ勘違いをする**（学習データも推論の癖も共通）。
`codex`（OpenAI）は別モデルなので盲点が構造的にズレる。**代替ではなく追加**として価値がある。

環境: `codex-cli 0.149.0` を `npm install -g @openai/codex`、ChatGPT アカウントでログイン済み。

### 必須の起動オプション（省略すると静かに誤った結果を返す）

```bash
codex review --uncommitted --config model_reasoning_effort=high \
  -c sandbox_mode='"danger-full-access"' \
  -c 'plugins."github@openai-curated".enabled=false'
```

1. **`sandbox_mode`** — Windows では codex のサンドボックスが機能せず、powershell / cmd /
   git bash の**すべての起動が `rejected: blocked by policy`** で失敗する。ローカル git を読めない。
   代償として codex は**サンドボックスなしでコマンドを実行できる**。レビュー用途に限定すること。
2. **`plugins."github@openai-curated".enabled=false`** — ローカルが読めないと codex は
   GitHub MCP にフォールバックし、**未push のローカル HEAD ではなくリモートの別コミットを
   レビューして「問題なし」と誤った合格を返した**（実際に発生）。

所要時間は実測 **約9分**。必ずバックグラウンドで走らせる。

### いつ回すか — 規模ではなく「壊れた時の影響範囲」

**Medium では回さない**（テンポを殺す）。Medium 以上の既定レビューは Claude の
`code-reviewer`（1〜2分）に任せ、Codex は次のカテゴリに触れる時だけ回す。

本番・デプロイ / DBスキーマ / 金銭に関わる計算 / 安全機構（hooks・guard）/ 認証・外部公開 /
アーキテクチャ変更。**差分が1行でも該当すれば回す。**

理由: 今回の PowerShell バイパスは変更規模としては Medium（設定ファイル1つ）だったが、
中身は全ての防御を無効化する穴だった。**危険さと差分の大きさは相関しない。**
規模を基準にすると、この種の「小さいが致命的」を取りこぼす。

### 初回レビューの成果 — 自分のセットアップから7件検出

| 重要度 | 指摘 | 判定 |
|---|---|---|
| P1 | guard の matcher が `Bash` のみ。**PowerShell ツールから破壊的コマンドが素通り** | 妥当 → 両対応に修正 |
| P1 | `git -C <path> reset --hard` が正規表現に一致しない（このリポジトリは `git -C` を多用） | 妥当 → グローバルオプション許容 |
| P1 | `rm -rf ./*` が一致しない（`.` 始まりのため） | 妥当 → 相対パス・ワイルドカードを追加 |
| P1 | `curl --data` / `--request POST` は `-X` 無しで POST するのに一致しない | 妥当 → 長形式と暗黙POSTを追加 |
| P2 | `tsc --noEmit` が追跡対象の `tsconfig.tsbuildinfo` を毎回書き換える | 妥当 → `--incremental false` |
| P2 | CLAUDE.md の起動手順が `--reload` を使っており、同じファイルの禁止ルールと矛盾 | 妥当 → 起動手順を修正 |
| P2 | `additionalContext` は `hookSpecificOutput` に入れるべき | **誤り** → 公式仕様でトップレベルが正しいと確認 |

**教訓**: レビュー結果を鵜呑みにしないこと。7件中1件は現行仕様と異なる指摘だった。
一方で、自分で書いた設定の穴（特に「もう一方のシェルから素通り」）は**自分では見つけられなかった**。

### 再発防止

`.claude/hooks/guard.test.mjs` を常設。ブロックすべき例と**通すべき例**の両方を含む53ケース。

```bash
node .claude/hooks/guard.test.mjs
```

ルールを変えたら必ず実行する（ブロック漏れだけでなく誤検知も検査する）。
