# jrvltsql 導入＆連携ガイド（自宅Windows PC）

`miyamamoto/jrvltsql`（Apache-2.0）を使って JV-Link → PostgreSQL のDB化を行う手順。
自前の固定長パースを避け、既製ツールにデータ取得・DB投入を任せる。

**前提:** `connect_test.py` の疎通テストが `[OK]` であること（JV-Link＋利用キーが有効）。

---

## 1. 動作要件（jrvltsql公式）

| 項目 | 要件 |
|------|------|
| OS | Windows 10 / 11 |
| Python | 3.10以上（JV-Link COM使用のため **32bit推奨**） |
| 契約 | JRA-VAN DataLab + 利用キー（取得済み） |
| PostgreSQL | PostgreSQL運用時のみ必要 |

> 利用キーは **JV-Link側に設定**（`JVSetUIProperties` ダイアログで一度設定すれば永続）。
> jrvltsql はその JV-Link 経由でデータを取得する。

## 2. インストール

```powershell
# 自動（PowerShell）
irm https://raw.githubusercontent.com/miyamamoto/jrvltsql/master/install.ps1 | iex

# もしくは手動
git clone https://github.com/miyamamoto/jrvltsql.git
cd jrvltsql
pip install -e .
```

## 3. 取り込み先PostgreSQLを用意（本アプリDBとは分離）

netkeibaデータと混ざらないよう、**JRA-VAN専用DB**を切る（同じPostgreSQLインスタンス内で別DB）。

```sql
CREATE DATABASE kbar_jravan;
CREATE USER ingestion_writer WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE kbar_jravan TO ingestion_writer;
```

接続情報は**環境変数**で渡す:

```powershell
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DATABASE="kbar_jravan"
$env:POSTGRES_USER="ingestion_writer"
$env:POSTGRES_PASSWORD="<password>"
```

## 4. 初回フルセットアップ（重い・1回だけ）

3か月契約の時計が動いているので**早めに実行**する。`--from`/`--to` で取得期間を指定。

```powershell
# 時系列オッズ含む（PostgreSQL）。期間は必要に応じて調整。
quickstart_timeseries.bat --db postgresql --from 20200101 --to 20260609
```

## 5. 日次/週次の差分同期

```powershell
daily_sync.bat --db postgresql
```

Windowsタスクスケジューラへ登録（例: 毎朝6:30）:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install_tasks.ps1 -DbType postgresql -Time 06:30
```

> 本アプリの `SCHED_JRAVAN_REMINDER_ENABLED=True` にすれば、週次のLINEリマインダーと併用可能。

## 6. 出力テーブル（jrvltsqlが作る）

| 種別 | テーブル |
|------|---------|
| レース詳細 | `NL_RA` |
| 出走馬・成績 | `NL_SE` |
| 払戻 | `NL_HR` |
| 確定オッズ（単複/馬連…） | `NL_O1` 〜 `NL_O6` |
| 公式時系列オッズ | `TS_O1`, `TS_O2` |
| 開催週速報オッズ | `TS_SOKUHO_O1` 〜 `TS_SOKUHO_O6` |

## 7. 本アプリ(VPS)との連携（本実装の次フェーズ）

1. 自宅PCの `kbar_jravan`（ステージング）に蓄積 → 週1で差分を本番VPSへ転送
2. **ID突合**: JV-Dataのレース/馬IDと netkeiba IDのマッピングテーブルを新設
   - 突合キー候補: 開催日 + 競馬場コード + レース番号、馬名、生年など
3. マッピング後、`NL_SE`/`NL_RA` の正確データで既存テーブルを補強 or 別カラムに併記
4. 学習データセットにJV-Data由来の特徴量を追加 → モデル再学習（Step 6と合流）

> 補足: 当日リアルタイムのオッズ/馬場は引き続き netkeiba スクレイピング（VPS完結）。
> JV-Dataの `TS_SOKUHO_*` 速報は自宅PC稼働時のみのため、リアルタイム用途には使わない。
