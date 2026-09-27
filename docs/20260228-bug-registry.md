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
| BUG-004 | 2026-09-27 | **デプロイ後に本番が全ページ 502** | nginx がアップストリーム名を**起動時に1度だけ**解決する。コンテナ再作成で backend/frontend の IP が**入れ替わった**のに古い解決結果を掴み続けた。`deploy.yml` は nginx reload を含む `deploy/deploy.sh` を呼んでいない | 未修正（`docker/nginx/nginx.conf` に resolver 追加が本筋） | `/` と `/api/v1/health` が 200 であること | 🔴 **応急復旧のみ。恒久対策は未実施** |

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

### BUG-004: デプロイ後に本番が全ページ 502（nginx が古い IP を掴む）

発覚: 2026-09-27（push→自動デプロイ直後の検証で実測）

**症状**: デプロイ直後、`/` も `/api/v1/health` も **502 Bad Gateway**。
一方 backend コンテナ内からアップストリームを直接叩くと **200** が返る。

**原因（実測で確定）**:

```
実際の IP     : backend=172.18.0.4 / frontend=172.18.0.5
nginx の向き先 : API  → 172.18.0.5:8000  ← frontend の IP
                画面 → 172.18.0.4:3000  ← backend の IP
```

nginx は `proxy_pass http://backend:8000;` のようにホスト名を直書きすると
**設定読み込み時に1度だけ名前解決し、その IP を保持し続ける**。
自動デプロイは backend と frontend を作り直すが **nginx は再起動しない**
（`Up 4 days` のままだった）。今回は再作成の順序が変わって
**2つの IP がちょうど入れ替わった**ため、API リクエストが frontend に、
画面リクエストが backend に飛んで両方 502 になった。

⚠️ **IP が入れ替わらず片方だけずれた場合は片側だけ 502 になる。**
運良く以前と同じ IP が再割当されれば何も起きない。
**だから今まで発覚しなかった＝再発するかどうかは運任せ。**

**応急対処（今回実施・復旧を実測確認）**: nginx の設定テスト＋reload。
reload は設定を再パースするので名前解決もやり直される。
実測で `/` と `/api/v1/health` の両方が 200 に復帰した。

**🔴 恒久対策（未実施・ユーザー判断待ち）**:

| 案 | 内容 | 評価 |
|---|---|---|
| **A: nginx に resolver を持たせる（本筋）** | `resolver 127.0.0.11 valid=10s;` を置き、アップストリームを**変数経由**にする（`set $up http://backend:8000; proxy_pass $up;`）。変数を使うと nginx は**リクエストごとに解決**する | 根本解決。nginx を触らずコンテナだけ入れ替えても追従する。ただし `docker/nginx/` 変更は規約上 `security-reviewer` + `codex` レビューが必要 |
| B: 自動デプロイの最後に nginx reload を入れる | 既存の `deploy/deploy.sh` は設定テスト＋reload を持っているが、**`.github/workflows/deploy.yml` はそれを呼んでいない** | 簡単だが `.github/workflows/` の更新には `workflow` スコープのトークンが必要（`~/.claude/CLAUDE.md` 参照）。またデプロイ以外でコンテナが再作成された時は守れない |
| C: 何もしない | 次のデプロイでまた運任せになる | 非推奨 |

**A と B は排他ではない。A が本筋で、B は保険。**

**E2E で検知できるようにする**: `frontend/e2e/production-health-check.spec.ts` は
502 を「データなし」系の警告として拾える可能性があるが、
**502 を明示的に検査していない**（未確認）。`/` と `/api/v1/health` の
ステータスコードが 200 であることを直接検査する項目を足すべき（PRV-003 候補）。

---

## 運用ルール

1. **本番デプロイ前**: `npx playwright test e2e/production-health-check.spec.ts --project=PC` を必ず実行
2. **新バグ発覚時**: このファイルにバグIDを追番で追加し、対応するE2Eチェックを `production-health-check.spec.ts` に追加
3. **定期チェック**: 開催日の朝にヘルスチェックを実行し、データ完全性を確認
