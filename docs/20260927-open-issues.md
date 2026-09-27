# 残課題（2026-09-27 時点・優先度順）

プロジェクトは「賭けて勝つ」目的では区切った（`20260927-project-retrospective.md`）。
**本番を止めるか動かし続けるかは未決定**なので、その判断で必要性が変わる課題がある。
各項目に **「アプリを畳む場合」の扱い** を書いてある。

---

## 🔴 P1: 本番が落ちうる / 安全機構に穴がある

### P1-1 `deploy.yml` が nginx を reload しない（構造的な欠陥）

- **現象**: 自動デプロイは backend/frontend を作り直すが nginx を触らない。
  bind mount した設定ファイルの中身が変わってもコンテナは再作成されないため、
  **nginx.conf を変更しても次の手動 reload まで反映されない**。
  2026-09-27 に IP 入れ替わりで本番が全ページ 502 になった（BUG-004）
- **今日入れた対策**: `docker/nginx/nginx.conf` を resolver + 変数経由に変更済み（`428a5fd`）。
  **手動 reload で有効化も完了**。これで IP 変更には追従する
- **まだ残っている穴**: 今後 nginx.conf を変更しても自動では反映されない。
  またデプロイ後のスモークテストが無いため 502 を検知できない
- **修正案**（`.github/workflows/deploy.yml` の末尾に追加）:
  ```bash
  docker compose --env-file .env -f docker/docker-compose.prod.yml exec -T nginx nginx -t
  docker compose --env-file .env -f docker/docker-compose.prod.yml exec -T nginx nginx -s reload
  # 反映確認（Basic認証が効いていること自体を検査に使える）
  test "$(curl -ksS -o /dev/null -w '%{http_code}' https://127.0.0.1/)" = 401
  ```
- ⚠️ **`.github/workflows/` の push には `workflow` スコープのトークンが必要**
  （ローカルの gh/GCM トークンは `repo` のみ）。回避策は `~/.claude/CLAUDE.md` 参照
- **アプリを畳む場合**: 不要（デプロイしなくなる）

### P1-2 デプロイ後のスモークテストが無い

- 2026-09-27 の 502 は**私が手で確認するまで誰も気づかなかった**。
  `deploy.sh` は `nginx -t` + reload を持っているが `deploy.yml` はそれを呼んでいない
- E2E ヘルスチェック（`frontend/e2e/production-health-check.spec.ts`）は
  **502 を明示的に検査していない**（未確認）。`/` と `/api/v1/health` が 200 であることを
  直接検査する項目を足すべき（PRV-003 候補）
- **アプリを畳む場合**: 不要

### P1-3 shitagoshirae の `.htpasswd.bak` が残っている

- `/opt/shitagoshirae/docker/nginx/.htpasswd.bak-20260917-000144`
- パスワードローテーション時のバックアップ。**旧ハッシュが残っている**
- 旧パスワードは無効化済みなので直接の危険は小さいが、**置いておく理由も無い**
- 対処: ユーザーが VPS 上で削除（`rm` 1回）。**別リポジトリなのでこちらからは触らない**
- **アプリを畳む場合**: shitagoshirae は別プロジェクトなので**畳んでも残る。対応必要**

---

## 🟡 P2: 品質・正確性（アプリを続けるなら必要）

### P2-1 本番の train/serve skew（過去走0走が 32.5%）

- **本番DBには 2026-02-22 より前のデータが 0件**。モデルは35年分の履歴で学習している。
  実測: 過去走0走 **32.5%** / 1〜2走 44.1% / **5走以上は 5.2%だけ**
- rolling 特徴量（`horse_avg_finish_5` 等）が本番ではほぼ機能していない
- 対処するなら: 学習データ（ローカルの161万件）を本番DBへ投入する、
  または予測時に履歴だけ別ソースから引く設計にする
- **アプリを畳む場合**: **対応不要。** ただし
  **「なぜ気づけなかったか」の教訓は retrospective §3-⑫ に記録済み**

### ✅ P2-2 JV-Link 日次同期が 106回連続失敗（2026-06-11 以降）→ **2026-09-27 に無効化済み**

- Windows タスク「KBar JRA-VAN Daily Sync」は **毎日12:00** 起動で、
  2026-06-11 20:30 を最後に成功せず 106回連続失敗（6月19 / 7月31 / 8月29 / 9月27回）
  ⚠️ 以前のメモにあった「朝6:30」は**誤り**。実測したトリガーは 12:00
- 失敗理由は `Failed to connect to PostgreSQL ... 127.0.0.1:5432`。
  実行時刻に Docker(PostgreSQL) が起動していないためと**推測**（実行時刻の Docker 状態は未実測）
- **JRA-VAN は未契約なので、そもそも取得できない状態**（2026-09-27 にマイページで確認）
- **✅ 対処済み**: タスクを **disable**（削除ではない）。実測で `Status: Disabled` /
  `Next Run Time: N/A` を独立確認（`schtasks /Query`）
- **戻し方**:
  ```powershell
  Enable-ScheduledTask -TaskName "KBar JRA-VAN Daily Sync"
  ```
  定義は `backend/jravan/KBar-JRA-VAN-Daily-Sync.task.xml` にエクスポート済み
  （ローカルパスを含むため gitignore。タスクごと消した場合は
  `Register-ScheduledTask -Xml (Get-Content <xml> | Out-String) -TaskName "KBar JRA-VAN Daily Sync"`）

### ✅ 週次リマインダー LINE は本番で**無効**だった（対応不要）

- 送信元は本番スケジューラの `job_jravan_reminder`（`backend/app/scheduler/jobs.py`）。
  金曜9:00 の CronTrigger だが、**登録は `SCHED_JRAVAN_REMINDER_ENABLED` に依存**
- **実測: 本番の稼働中プロセスで `False`。スケジューラに jravan 関連ジョブは0件**
  → **LINE は届いていない。本番側の変更は不要**（当初「毎週届き続ける」と書いたのは誤り）

### P2-3 バッチの失敗が通知されない

- JV-Link 同期が3.5ヶ月失敗し続けたのに気づかなかった直接の原因。
  証明書更新は失敗時に LINE へ 🔴 を飛ばす作りになっているのに、他のバッチには無い
- **アプリを畳む場合**: 不要。ただし**次のプロジェクトでは最初から入れる**（教訓）

### P2-4 `oddsfree.py` 以外にまだ位置ベースの検証分割が残っている

- `scripts/phase2_pace_backtest.py` が `iloc` ベースの分割を使っている（未修正）。
  `trainer.py` と `oddsfree.py` は日付ベースに修正済み
- **アプリを畳む場合**: 不要（使い捨てスクリプト）

---

## 🟢 P3: 整理・低リスク

### P3-1 `.github/workflows/test.yml`（CI でテストを走らせる）が未適用

- 差分案は `20260927-ci-test-workflow-proposal.md` にある。`workflow` スコープが必要で未適用
- **アプリを畳む場合**: 不要

### P3-2 `frontend/test-results/` が gitignore されておらず溜まり続けている

- Playwright の実行成果物が未追跡ファイルとして7ディレクトリ分残っている。
  `git add` のたびに巻き込むリスクがある（**実際に私が2回、別の未追跡ファイルを巻き込んだ**）
- 対処: `.gitignore` に `frontend/test-results/` を追加
- **アプリを畳む場合**: 低優先だが1行なのでやってよい

### P3-3 `docs/20260711-development-story-techblog.md` が未追跡のまま

- ユーザーのファイル。**私が2回誤ってコミットに巻き込み、2回外した**（`f391026` / `f8060e1` 後）。
  コミットするかはユーザー判断
- **アプリを畳む場合**: ユーザー判断

### P3-4 `nginx.bootstrap.conf` に旧 upstream 方式が残っている

- 証明書取得までの数分しか使わない短命用途なので**意図的に据え置き**、
  理由をファイル冒頭に明記済み（`66189c8`）。対応不要だが記録として残す

### P3-5 mutation testing で未解決だった項目

- `features.py` のテスト強化について、test-reviewer が指摘した2つの mutation
  （先頭行のみの assert / 複合キーの2つ目）の検出は**確認できていない**。
  テストは追加したが穴が閉じた確証は無い（`20260927-feature-leakage-bug.md` に記載済み）
- **アプリを畳む場合**: 不要

---

## 本番の扱いを決めたら変わること

| 判断 | 必要になる作業 |
|---|---|
| **A 止める** | DB を pg_dump でバックアップ → コンテナ停止。P1-3 は実施（P2-2 は済） |
| **B データ収集だけ残す** | 予想生成・LINE通知ジョブを止める。P1-1/P1-2 は入れたほうがよい（落ちても気づけないため）。`odds_snapshots` の蓄積が継続 |
| **C 現状維持** | P1-1 / P1-2 / P2-1 / P2-2 すべて対応が望ましい |
| **D 整理のみ** | P1-3 と P2-2 だけ |

**どの案でも共通して必要**: ~~P2-2~~（**2026-09-27 に無効化済み**）と **P1-3（`.htpasswd.bak` 削除）**。
→ **残っているのは P1-3 だけ**（別リポジトリなので VPS 上でユーザーが `rm` 1回）。
