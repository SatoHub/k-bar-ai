# 競馬AI予想アプリ 進捗管理

**最終更新:** 2026-06-12（血統・確定オッズ/払戻を自己完結テーブル化しVPS本番表示を達成。#3モデル再学習が次）

---

## 🔵 次回開始ガイド（RESUME HERE — まずここを読む）

### 今日(2026-06-12)の到達点（git push済み / 最新コミット `3a179a2`）
**共通設計＝「JV-Data由来データを自己完結テーブル化→pg_dumpでVPS同期」（FDW非依存）。**
本番racesは2/21〜6/14でJV-Data(5/9〜)と日付が重なるため race_id/netkeiba_id で結合可能。
同期は `backend/jravan/sync_jravan_derived_to_vps.sh`（血統+確定オッズ+払戻の3表を一括・冪等）。

- ✅ **#1 血統の本番表示を達成**: 自己完結テーブル `horse_pedigree`(`netkeiba_id=kettonum`キー)。
  エンドポイントをFDW直結→ローカルテーブル参照に変更。本番で血統表示を実証
  (race 202610011106・ハービンジャー等8頭)。alembic `e5f6a7b8c901`。
  populate=`sql/populate_horse_pedigree.sql`(2729件)
  - ⚠️ **カバレッジ現状2729頭(直近26%)**。`option 1`(差分)では日付非重複の壁で増えない。
    UM全馬セットアップ(`--spec DIFF --option 3/4`)が唯一の根本解。後日→populate再実行→再syncで向上
- ✅ **#2 確定オッズ・払戻の本番表示を達成**: 自己完結テーブル `confirmed_win_odds`/`confirmed_payouts`
  (race_idキー・アプリraces非依存)。API `GET /races/{id}/confirmed`、フロント `ConfirmedResults.tsx`
  (払戻を枠色バッジ+確定単勝オッズ表)をレース詳細に追加。本番で実証(race 202604010301・払戻/オッズ)。
  alembic `f6a7b8c9d012`、populate=`sql/populate_confirmed_jravan.sql`
  - 🔴 **重要発見**: 「31%」は前日の古い計測(ローカルアプリDB 3/1止まり×JV-Data 5/9〜の非重複)。
    O1確定オッズ取得自体は本体期間99%機能。**単独`--spec O1`は契約上不可(JVOpen -111)**。
    ただし**RACE再取得で確定オッズは回復可能**と実証(5/30が0→24/24)。本体5/9〜6/7のRACE再取得を実行中
    (現状156→順次回復)。完了後 populate_confirmed_jravan.sql 再実行→再sync で本番カバレッジUP
- ⚠️ **本番APIはBasic認証**(`-u admin:kbar2026ai`)。疎通確認時は付与すること
- ⚠️ **uvicorn --reloadは重い**(scheduler起動)。プロセス二重化・孤立ワーカーに注意(継承ソケット)。
  ローカルは `uv run uvicorn app.main:app --port 8000`(reloadなし)推奨

### 前日(2026-06-11)の到達点（コミット `ec97566`）
- ✅ JRA-VAN本番DB化 / ID突合(レース72/72・馬1027/1027) / 過去5走馬柱 / 全8券種オッズ枠色バッジ

### 次回やること（優先度順）★ここから再開
1. ✅ **血統を本番でも表示**（2026-06-12完了。(a)カバレッジ向上=UMセットアップ時に後日）
2. ✅ **確定オッズ・払戻を本番でも表示**（2026-06-12完了）
   - 個別RACE再取得で確定オッズ 156→**242レース**にカバレッジUP（本番に同期済・全242が本番racesと結合）
   - ⚠️ **複数日一括RACE取得はオッズを回復しない**。**1日ずつ個別取得が必須**（5/30/5/31は0→24に回復）。
     5/10・6/3・6/4等は個別取得でも0＝サーバー側でその日の確定オッズ取得不能（保持期間切れ等）。直近は100%
3. 🟡 **ID突合データでモデル再学習**（JV-Dataの正確データ＋確定オッズを特徴量化）← 次はここ
4. 🟡 **④ 馬場状態（含水率・クッション値）**＝JRA公式「馬場情報」ページ専用→新規スクレイパー新設（開催日のみ）
5. 🟢 運用: 旧PAT `ghp_a2SL...` のRevoke / deploy.ymlのpull失敗検知(`set -e`等・未対応)

### 再開コマンド（環境起動・JRA-VAN取得）
```powershell
# 自宅PCでJRA-VAN取得する場合（32bit venv・PYTHONUTF8必須）
$env:PYTHONUTF8="1"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_PORT="5432"
$env:POSTGRES_DATABASE="kbar_jravan"; $env:POSTGRES_USER="kbar"; $env:POSTGRES_PASSWORD="kbar_dev_password"
cd C:\Users\unoen\projects\k-bar-ai\backend\jravan\jrvltsql
..\.venv32\Scripts\python.exe -m src.cli.main fetch --from YYYYMMDD --to YYYYMMDD --spec RACE --option 1 --db postgresql --no-cache
```
- FDWマッピング再適用: `docker exec -i kbar-postgres psql -U kbar -d kbar < backend/jravan/sql/jravan_fdw_mapping.sql`
- ⚠️ jrvltsql再clone時は `jrvltsql-setup.md` §0 のパッチ(JVRead -402/-403回復)を必ず再適用

---

## 🟢 2026-06-11 セッション成果 ＝ JRA-VAN本番DB化（詳細）

> **今日やったこと:** JRA-VANデータを確定オッズ込みでPostgreSQL(`kbar_jravan`)へ本番投入し、
> 日次自動同期までを完成。途中、jrvltsqlの**致命バグを特定・修正**して取得を完走させた。

### 完了した4ステップ
1. **`kbar_jravan` DB作成** — `kbar-postgres`(localhost:5432)内、アプリDB`kbar`と分離。74テーブル作成。
2. **PostgreSQL接続検証** — config.yamlの`database`を`${POSTGRES_DATABASE:kbar_jravan}`に環境変数化。
3. **確定オッズ込み本番フル取得** — `fetch --spec RACE --option 1 --db postgresql`で
   2026-05-09〜06-07の**312レース**を投入（**1,344,842件・Failed=0**）。
   NL_RA(312)/NL_SE(4448)/NL_HR(312,全レース払戻あり)/NL_O1〜O6(確定オッズ)が揃った。
4. **日次同期の自動化** — `jravan_sync.bat`をPostgreSQL向けに書換え、Windowsタスクスケジューラに
   「KBar JRA-VAN Daily Sync」を**毎朝6:30**で登録。end-to-end検証済み
   （RACE 218,200件＋DIFN 4,601件・Failed=0）。`--days-back 7`で実行漏れも翌日補完。

### 🔴 重要バグ修正（jrvltsql本体・再clone時に再適用が必要）
> `backend/jravan/jrvltsql/` は`.gitignore`済み＝git管理外。下記パッチは**再cloneで消える**。
> 詳細は `backend/jravan/jrvltsql-setup.md` 冒頭「§0 再clone時に必ず再適用するローカルパッチ」参照。
- **パッチA（必須）:** `src/jvlink/wrapper.py` の `jv_read()` が、本来`fetcher/base.py`が
  「破損ファイル削除→続行」で回復できる**JVRead -402/-403等も即raise**し、本番取得が途中
  クラッシュしていた。→ 回復可能コードは`return result, None, filename_str`する分岐を追加。
- **パッチB:** config.yamlの取込先DBを環境変数化（上記2）。
- **実行時の注意:** `PYTHONUTF8=1` 必須（cp932コンソールだとログの`—`等で`UnicodeEncodeError`クラッシュ）。
  `.bat`は**ASCII限定＋CRLF**で書くこと（cmd.exeはOEMコードページで読むため日本語UTF-8は文字化け誤実行）。

### ✅ ID突合 完了（2026-06-11・決定的マッピング実証＋FDW実装）
**結論: 確率的マッチ不要・完全一致キーで突合できる**（netkeiba IDがJRA公式コード由来のため）。
- **レース突合**: `race_id = 年‖lpad(JyoCD,2)‖lpad(回次,2)‖lpad(日次,2)‖lpad(R,2)` = アプリ`races.race_id`
  → 2026-02-21/22で **72/72 完全一致**（ミスマッチ0）
- **競走馬突合**: JV-Data `NL_SE.kettonum`(血統登録番号) = アプリ`horses.netkeiba_id`
  → **1027/1027 完全一致**
- ⚠️ アプリ`races.racecourse_code`は**空**。競馬場コードはrace_id内に埋込（上式で対応）
- ⚠️ アプリDBは〜2026-03-01、JV-Dataは2026-05-09〜で**日付が現状非重複**。検証用に2月週末を別途取得済み

**実装（postgres_fdw・同一PG内別DBを結合）**: `backend/jravan/sql/jravan_fdw_mapping.sql`
- アプリDB`kbar`に`jravan`スキーマ＋外部テーブル（FDWで`kbar_jravan`参照）
- `jravan.build_race_id()` 関数 / `jravan.v_confirmed_payouts`（払戻・race_idキー）/
  `jravan.v_confirmed_win_odds`（確定単勝・race_id+馬番キー）
- 検証: アプリ races×払戻 = **72/72**、馬レベルのオッズJOINも実値一致（メビウスロマンス2.9倍等）
- カバレッジ: 498レース中 払戻384(77%) / 確定単勝オッズ156(31%)
- 適用: `docker exec -i kbar-postgres psql -U kbar -d kbar < backend/jravan/sql/jravan_fdw_mapping.sql`

### 次にやること（JRA-VAN活用フェーズの続き）
- [ ] **O1確定オッズのカバレッジ改善**（datakubun=5の取得が部分的＝31%。`fetch --spec O1`等の追加取得を検討）
- [ ] 突合を使い`NL_SE`/`NL_RA`の正確データ＋確定オッズで学習データセットを補強→モデル再学習
- [ ] アプリのレース詳細/結果ページで確定払戻・確定オッズをJV-Data由来で表示（FDWビュー利用）
- [ ] VPS本番への展開（現状ローカルのみ。FDWは自宅PCのkbar_jravanに依存→転送方式を設計）
- [ ] （任意）過去2021〜2026ヒストリカル一括取得（重い・契約3ヶ月の時計に注意）

### 優先項目（ユーザー指定・1から順に）
1. ✅ **ID突合**（上記・完了）
2. ✅ **過去5走の馬柱**（2026-06-11完了）
   - backend: `GET /races/{race_id}/past-performances?limit=5`（`race_service.get_past_performances`、
     ウィンドウ関数ROW_NUMBERで全出走馬の現レース日より前の直近N走を1クエリ取得＝N+1回避）
   - schema: `PastRaceRecord`/`HorsePastPerformances`/`PastPerformancesResponse`（schemas/race.py）
   - frontend: `EntryTable.tsx`に折りたたみ馬柱（`pastByHorse`プロップ、`PastRacesPanel`、全開閉ボタン）。
     レース詳細ページで並行fetch（`fetchPastPerformances`）。tsc型クリーン
   - データ源=アプリDB自身の過去race_entries+races。実値検証OK（200909010710で着順/上3F/通過/オッズ取得）
   - 注: 3歳新馬等は過去走なし→空表示。古いレースはhead_count(頭数)欠損あり
3. ✅ **全8券種オッズタブ**（既実装と判明）: `AllOddsTabs.tsx`がレース詳細(page.tsx:344)で全8券種
   レンダリング済み。`GET /races/{id}/odds/table`は確定オッズ(status=result)を返す。上の単勝テーブルは
   「ライブ単勝＋更新ボタン＋変動グラフ」で役割が異なり重複ではない→現状維持
4. [後回し] **馬場状態（含水率・クッション値）** ＝ ⚠️**ユーザー判断で後回し**:
   - JV-Data DataLabには**含水率・クッション値が無い**（馬場はコード=良/稍重/重/不良のみ。`nl_wf`はWIN5）
   - 含水率・クッション値はJRA公式「馬場情報」(jra.go.jp/keiba/baba/)のみ＝**新規スクレイパー必要・開催日のみ・過去遡及不可**
   - 再開時は専用スクレイパー新設から。本日(木)は実データ検証不可のため見送り

### ✅ 血統（父/母/母父）表示（2026-06-11・#4の代替として実装）
本日のFDW突合を活用。JV-Data NL_UM(3代血統)を `jravan.v_pedigree`（父=ketto3infobamei1/
母=2/父父=3/母父=5）でビュー化し、`netkeiba_id=kettonum`でアプリhorsesと突合。
- backend: `GET /races/{race_id}/pedigree`（`race_service.get_race_pedigree`、text SQLでFDWビューJOIN・
  FDW不通時は空でグレースフル）。schema `HorsePedigree`/`RacePedigreeResponse`
- frontend: `fetchPedigree`、EntryTableの馬名下に「父 / 母父」小字表示（`pedigreeByHorse`プロップ）
- 実値OK（サトノクラウン/母父ネオユニヴァース等）。**カバレッジ257/1027(25%)**＝`fetch --spec RACE`は
  UM馬マスタを含まずNL_UMがDIFN同期分のみのため。**改善策: DIFF/UM一括取得**（daily DIFN同期で漸増）
- SQLは `backend/jravan/sql/jravan_fdw_mapping.sql` に追記（nl_um外部テーブル＋v_pedigree）

### 主要ファイル早見表（JRA-VAN）
- `backend/jravan/jravan_sync.bat` — 日次同期ラッパー（PostgreSQL向け・.gitignore済み）
- `backend/jravan/jrvltsql-setup.md` — 導入手順＋再cloneパッチ（§0必読）
- `backend/jravan/jrvltsql/` — jrvltsql本体（git管理外）。DB=`kbar_jravan` user=`kbar`
- 取得コマンド: `python -m src.cli.main fetch --from YYYYMMDD --to YYYYMMDD --spec RACE --option 1 --db postgresql --no-cache`

---

## 🟢 2026-06-10（夕方）セッション成果 ＝ 馬券UI改善

> **今日やったこと:** 馬券まわりのUI/UXを5件改善し、すべて本番反映済み（GitHub Actions自動デプロイ成功）。
> バックエンド変更なし、フロントエンド（`frontend/src/`）のみ。最終コミット `a10b62b`。

### 本番反映した5件（すべてデプロイ成功）
1. **レース一覧の検索フィルターバー削除**（`app/races/page.tsx`）
   - 年月/週/日付指定/競馬場の検索欄を撤去し、**日付選択をカレンダー一本化**。
   - 競馬場の絞り込みは既存の競馬場タブが担当。`RaceFilters.tsx` は削除。
2. **流しに「軸頭数・着固定・マルチ」を追加＝ネット馬券(JRA即PAT)の全方式に対応**
   - `lib/betCalculations.ts` に `getNagashiPatterns(picks, ordered, axisCount)` を新設。
     馬単=1着/2着/マルチ、三連複=軸1頭/軸2頭、三連単=1/2/3着・軸1頭マルチ／
     1・2/1・3/2・3着・軸2頭マルチ。**点数式はJRA公式12ケースで検証済み**。
   - `BetMethodComparison.tsx` に軸頭数上限(picks-1)・①②順バッジ・流しパターン選択UIを追加。
3. **馬券シミュレーターの複数買いを「買い目別オッズ自動取得＋個別賭け金配分」に**（`BettingSimulator.tsx`）
   - 代表オッズの手入力を**廃止**。`fetchOddsTable()` で全組オッズを自動取得し、
     `ComboBreakdown` で買い目ごとに一覧（オッズ/掛け金/的中時払戻）。
   - 買い目ごとに**掛け金を個別配分**可能。slot状態に `comboAmounts`/`comboOdds` を追加。
     既定=「1点あたり掛け金」、「均等に戻す」でリセット。保存・集計も買い目別。
4. **買い目一覧を枠色付き馬番バッジ表示に**（シミュレーター）
   - 横長な馬名テキスト→JRA公式の枠色(1白2黒3赤4青5黄6緑7橙8桃)バッジ。三連単は「→」、
     馬名はホバーtitle、行は縞模様。
5. **組数・オッズ比較の組み合わせ一覧も枠色バッジ化＋共通化**
   - バッジを `components/ComboBadges.tsx` 共通コンポーネントに切り出し、両画面で共用
     （`size="md"`=比較画面 / `"sm"`=シミュレーター）。

### 次にやること（馬券UIの続き・優先度順）
- [ ] **動作確認（実機）:** 本番 `/races/{id}/simulate` で複数買い→買い目別オッズ自動取得・
      個別配分・枠色バッジが正しく出るか目視（Ctrl+Shift+Rでキャッシュクリア）。発売前/締切後は
      オッズ「—」になる点に注意（確定オッズは過去レースで確認可）。
- [ ] **フェーズ1残:** レース詳細ページのオッズ表示を単勝のみ→**全8券種タブ表示**（旧task#6）。
- [ ] **フェーズ2:** JRA-VAN速報の自宅PC→VPS中継＋netkeiba自動フォールバック（source列＋バッジ）。
- [ ] （任意）`slot.showCombinations` が未使用フィールドとして残存。気になれば除去。

### 主要ファイル早見表（馬券UI）
- `frontend/src/lib/betCalculations.ts` — 組合せ計算＋`getNagashiPatterns`（流し全方式）
- `frontend/src/components/BetMethodComparison.tsx` — 組数・オッズ比較UI（券種×買い方）
- `frontend/src/components/BettingSimulator.tsx` — 馬券シミュレーター（複数スロット・買い目別配分）
- `frontend/src/components/ComboBadges.tsx` — 枠色バッジ共通コンポーネント
- API: `GET /races/{id}/odds/table?bet_type=`（全組オッズ）, `POST /races/{id}/odds/combo`（1組）

---

## 🟢 2026-06-10（日中）セッション成果

### A. jrvltsql 導入＆パイプライン検証（自宅PC・32bit venv）
- ✅ `backend/jravan/jrvltsql` をclone、`.venv32`へ `pip install -e .` 済み
- ✅ **重要修正:** `pg8000`（純Python・32bit対応PGドライバ）必須。SQLite利用時も
  `src/database/__init__.py` がPGハンドラを無条件importするため、未導入だと
  「テーブル作成失敗」で落ちる → `..\.venv32\Scripts\python.exe -m pip install pg8000`
- ✅ 74テーブル作成成功。**通常データ取込は正常**（NL_RA/SE/UM/BN等 12,076件・失敗0）
- ⚠️ **確定オッズ(NL_O1〜6)・払戻(NL_HR)は `quickstart --mode update` では入らない**
  - 差分モードはマスタ＋出馬表のみ。**確定オッズは `fetch --spec RACE` が必要**：
    ```powershell
    cd backend\jravan\jrvltsql
    ..\.venv32\Scripts\python.exe -m src.cli.main fetch --from 20260509 --to 20260609 --spec RACE --option 1 --db sqlite
    ```
  - O1=単複枠 / O2=馬連 / O3=ワイド(幅) / O4=馬単 / O5=三連複 / O6=三連単
- ⚠️ `--include-timeseries`(0B41/42) は過去レース個別取得で激遅＆read_count=0が多い。
  本番一括では使わず、確定オッズは `fetch --spec RACE` を使う方針

### B. 全券種オッズ・全買い方の組数比較UI（フェーズ1・netkeiba主体）
> 方針: 当日ライブのオッズは **netkeiba**（VPS24h・PC不要・既に8券種解析可）が主。
> JRA-VANは過去確定・AI精度補強担当。将来フェーズ2で「PC起動時JRA-VAN速報→VPS中継、
> 消えてればnetkeibaにフォールバック」のハイブリッド化（source列＋バッジ）。
- ✅ backend `parse_full_odds()`（odds.py）: 券種の全組オッズを返す（ワイド幅対応）
- ✅ backend `scrape_full_odds()`（netkeiba.py）: 券種1回で全組取得
- ✅ backend `GET /races/{id}/odds/table?bet_type=`（races.py / schema OddsTableResponse）
- ✅ front `BetMethodComparison.tsx` 新規: 8券種×全買い方(通常/ボックス/フォーメーション/流し)
  の**組数比較**＋**各組オッズ一覧**（合計点数・最小/最大/平均・払戻目安）。`betCalculations`活用
- ✅ `simulate/page.tsx` に組込み。tsc型チェック通過（既存e2eの無関係エラーのみ）
- [ ] **フェーズ1残:** レース詳細ページの単勝のみ表示→全8券種タブ表示（task#6）
- [ ] **フェーズ2:** JRA-VAN速報の自宅PC→VPS中継＋自動フォールバック

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
