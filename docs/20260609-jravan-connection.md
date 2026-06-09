# JRA-VAN データ連携 接続方式 調査結果

調査日: 2026-06-09 / 対象アプリ: K-Bar AI（Python/FastAPI + PostgreSQL）

---

## 1. JRA-VAN のデータ提供サービスの種類と料金

### JRA-VAN Data Lab.（データラボ）
- **月額料金: 2,090円（税込）使い放題**。どれだけデータを取得しても追加料金は発生しない（2026年時点）。
- データラボ自体は「ソフト」ではなく、**JRAの巨大DBサーバへ接続する「権利（鍵）」と、データを運ぶ「パイプ役（JV-Link）」を提供するサービス**。契約だけでは画面に何も映らず、100種類以上ある「対応ソフト」または自作プログラムを通じて初めて機能する。
- 契約に必要なもの: **JRA-VAN会員登録 + Data Lab.契約 + 利用キー（英数字17桁の認証キー）の購入**。

### 個人開発者向けプラン
- 個人開発者でも **Data Lab.（月額2,090円）1本で過去データ（蓄積系）とリアルタイムデータの両方が取得可能**。専用の高額プランは不要。
- 提供データ「JV-Data」には、レース情報・競走馬情報に加え、**馬体重・オッズなどのリアルタイム情報**も含まれる。
- データには大きく2系統あり、自作アプリ側で使い分ける:
  - **蓄積系データ（セットアップ/通常データ）**: 過去の確定データ。初回はフルセットアップで大量の過去データを取得。
  - **速報系/リアルタイムデータ**: 開催当日のオッズ・馬体重・払戻など。

---

## 2. 接続方式（最重要）

### JV-Link とは
- **JRA-VAN Data Lab. を利用するための唯一の公式インターフェースモジュール**。自作ソフトは JV-Link を介して JV-Data サーバから各種データを取得する。
- 実体は **ActiveX COM コンポーネント（`JVLink.ocx` / ProgID = `JVDTLab.JVLink`）**。ユーザ認証・データ要求・圧縮ファイルの取得/保存/解凍までを一括で処理する。

### 動作要件（Windows 必須）
- **Windows 専用**。Windows 10 / 11（32bit・64bit OS両対応）、**日本語版のみ**。Windows RT / Mobile は非対応。
- **Mac / Linux / クラウド（Linuxコンテナ）では直接動作しない**。COM/ActiveX は Windows 固有技術のため、本番の Linux VPS 上では使えない。これが「方式C（自宅Windows PCで同期）」が必然となる根拠。
- **重要な落とし穴: JV-Link は 32bit ActiveX**。64bit アプリから直接は呼べず、後述の DllSurrogate 回避策が必要。
- 補足: 近年は公式SDKに `JVLink.ocx`（ActiveX単体）が同梱されない／配布停止との情報があるが、**JV-Link本体（COMサーバ）は SDK/インストーラ経由で導入可能**。

### 認証方式
- **利用キー（英数字17桁）** を JV-Link の `JVSetUIProperties` / `JVSetServiceKey` 等で設定し、ユーザ認証を行う。キーは JRA-VAN から購入。

---

## 3. Python からの連携可否

### 結論: 可能（ただし非公式・Windows上限定）
JRA-VAN は Python を公式サポートしていないが、有志により **pywin32（win32com）経由のCOM呼び出し**で実用的に動作することが確立している。

### 呼び出し方法
```python
import win32com.client
jv = win32com.client.Dispatch('JVDTLab.JVLink')
# 基本フロー: JVInit → JVOpen → JVRead → JVClose
# 戻り値はタプルで返る（Python COMの仕様）
```
- 速報系は `JVRTOpen` / `JVGets`、リアルタイム情報の取得にも対応。

### 32bit/64bit 問題と回避策
- JV-Link は 32bit のため、**素直に使うなら 32bit Python が推奨**。
- 64bit Python から使う場合は **DllSurrogate**（Windowsのアウトプロセス COM サーバ機構）を利用:
  1. `HKEY_CLASSES_ROOT\Wow6432Node\CLSID` に JV-Link の CLSID キーを追加
  2. 対応する `AppID` キーを作成し、`DllSurrogate` 値を空文字で設定
  3. `.reg` ファイルをマージ
  → これで 64bit `dllhost.exe` が 32bit COMサーバを仲介し、64bit Python から利用可能になる。

### 実在する OSS / ラッパー（GitHub等）
| 名称 | 内容 | URL |
|---|---|---|
| **miyamamoto/jrvltsql** | **本件に最も近い。** JRA-VANデータを **SQLite/DuckDB/PostgreSQL にインポートする Python ツール**。Windows 10/11専用、Python 3.10+、Apache-2.0。環境変数で接続情報を設定し `quickstart_timeseries.bat` で初期構築、`daily_sync.bat` で日次同期。 | github.com/miyamamoto/jrvltsql |
| **miyamamoto/jvlink-mcp-server** | JVLinkToSQLite DB を解析する MCP サーバ（Claude等のAI連携用） | github.com/miyamamoto/jvlink-mcp-server |
| **cariandrum22/Xanthos** | F# 製の型安全 JV-Link COMラッパー（Python外だが設計参考に） | github.com/cariandrum22/Xanthos |
| **HRAPS** の Python(64bit) JV-Linkラッパークラス | note記事。馬体重・払戻の速報、JVGets対応。64bit対応実装例 | note.com/hraps/n/ne756e8a041b3 |

### 取得データのフォーマットとパース概要
- JV-Data は **固定長レコード（Shift-JIS）**。`JVRead` が返す1行を「JV-Data仕様書」のバイト数定義に従ってスライスして各項目を抽出する。
- 取得対象は **データ種別（DataSpec）+ レコード種別ID（RecordTypeId）** で指定。
- 蓄積系では「通常データ＋今週データ」か「セットアップデータ」を選択。**バイト境界はマルチバイト前提なので Shift-JIS バイト配列のまま分割する**点が実装上の注意。
- 公式コード表/仕様（例: `JV-Data4512.xlsx`）が JRA-VAN SDK で配布されており、これがパース定義の一次資料となる。

---

## 4. JRA-VAN 以外の選択肢（参考）

- **JRA-VAN NEXT**: JRAシステムサービス提供の「オールインワン専用ソフト」。インストール即プロ並み環境が揃うが、**完成品ソフトでありデータをプログラムから取り出す用途には不向き**。自作AI開発には Data Lab. が正解。
- **地方競馬DATA（UmaConn）**: 地方競馬（NAR）向けの別系統データサービス。JRA（中央）のみ扱う本アプリでは当面不要。
- JV-Data を中継する既存OSSツール（**EveryDB2 / JVLinkToSQLite** など）もあり、自前パースを避けて「ツールがDB化したものを読む」構成も選択肢。

---

## 5. 方式C（自宅Windows PCで週1同期 → PostgreSQL）の妥当性チェック

**結論: 技術的に十分成立する。むしろJV-LinkがWindows/COM専用である以上、これが事実上の唯一の現実解。**

実証例として **jrvltsql が「Windows + Python + JV-Link → PostgreSQL」をそのまま実現**しており、`daily_sync.bat` 相当の日次/週次同期も標準機能として存在する。

### 想定される落とし穴・注意点
1. **Windows必須・Linux本番では動かない**: JV-Link取得処理は必ず自宅Windows PC側に隔離。本番Linux VPSへはデータ（DBダンプ/差分）だけを転送する設計にする。
2. **32bit COMの制約**: 64bit Pythonを使うなら DllSurrogate のレジストリ設定が必須。手間を避けるなら取得専用に **32bit Python venv** を切る方が堅実。
3. **初回フルセットアップが重い**: 過去全データのセットアップは取得・解凍に時間とディスクを要する。初回は数時間〜規模次第で長時間かかる前提でバッチ化する。
4. **固定長/Shift-JISパース**: 仕様書ベースのバイト分割が必要。自前実装はバグの温床になりやすいので、jrvltsql等の既存OSSを流用するのが安全。
5. **PC稼働依存**: 自宅PCが起動していないと同期が走らない。週1運用なら許容範囲だが、タスクスケジューラ + 失敗通知（既存のLINE通知ジョブと連動可）を用意すべき。
6. **データ整合性**: netkeibaスクレイピングデータとJV-Dataの突合（レースID・馬IDのマッピング）設計が別途必要。両者は識別子体系が異なる。

---

## 推奨アーキテクチャと次のステップ

1. **取得層は自宅Windows PCに隔離する**: JV-Link呼び出し専用の小さなPythonバッチを作り、本番FastAPI（Linux VPS）からは完全分離。JV-Linkに触れるのはこのPCのみとする。

2. **車輪の再発明を避け `miyamamoto/jrvltsql`（Apache-2.0）を第一候補に評価する**: 「Windows + JV-Link → PostgreSQL」「日次/週次同期」という要件にほぼ一致。これをそのまま採用 or フォークし、自前の固定長パース実装は最小化する。

3. **64bitを使うなら DllSurrogate、避けるなら32bit Python venv**: 既存スタックが64bitなら取得バッチ専用に **32bit Python環境を別途用意**するのが最も事故が少ない（DllSurrogateのレジストリ設定は環境再現性が低いため）。

4. **「JV-Data用ステージングDB → 本番への差分連携」の二層構成にする**: 自宅PCのPostgreSQL（またはSQLite/DuckDB）に蓄積 → 週1で差分を本番VPSへエクスポート/インポート。netkeibaデータとは別テーブルに格納し、後段でレースID・馬IDのマッピングテーブルを設けて突合する。

5. **同期の自動化と失敗監視を組む**: Windowsタスクスケジューラで週1実行 + LINE通知ジョブと連携し、初回フルセットアップは別バッチ・別スケジュールで一度だけ重く回す設計にする。契約は **Data Lab. 月額2,090円 + 利用キー17桁** を取得すればすぐ着手可能。

---

### 主要ソース
- JRA-VAN データラボ 公式: https://jra-van.jp/dlb/ / 料金FAQ: https://support.jra-van.jp/jravan/detail?site=SVKNEGBV&id=24
- JV-Link システム概要（開発者コミュニティ）: https://developer.jra-van.jp/t/topic/49 / 利用キー取得: https://developer.jra-van.jp/t/topic/693
- Python(64bit)でJV-Link(32bit)を使う / DllSurrogate（Qiita）: https://qiita.com/hraps/items/594936369b5f0c856a8f
- PythonからJV-Linkを操作する（Zenn）: https://zenn.dev/nozele/articles/c64e456d0c77e4
- miyamamoto/jrvltsql（PostgreSQLインポート, Apache-2.0）: https://github.com/miyamamoto/jrvltsql
- miyamamoto/jvlink-mcp-server: https://github.com/miyamamoto/jvlink-mcp-server
- HRAPS Python(64bit) JV-Linkラッパークラス（note）: https://note.com/hraps/n/ne756e8a041b3

---

## 接続手順（ゼロから初接続まで）

> ①〜③はユーザー操作（アカウント・支払い・インストール）。④以降はコードで対応可能。
> 環境: 自宅 Windows 11 PC（JV-Link動作要件を満たす）。

### STEP 1: JRA-VAN会員登録（無料）
1. https://jra-van.jp/ で会員登録（メール・パスワード）
2. 無料会員でOK（この時点では課金なし）

### STEP 2: Data Lab. を契約（月2,090円）
1. JRA-VANサイトで「データラボ（Data Lab.）」を申し込む
2. 支払い方法を登録 → 月額2,090円使い放題

### STEP 3: 利用キー（17桁）を取得
1. Data Lab.契約後、マイページ等で **利用キー（英数字17桁）** を発行/購入
2. このキーがJV-Linkの認証に必須。控えておく

### STEP 4: JV-Link（SDK）を自宅Windows PCにインストール
1. JRA-VANの開発者ページ/SDKページから JV-Link インストーラを入手
2. インストール実行（COMコンポーネント `JVDTLab.JVLink` が登録される）
3. SDK同梱の「JV-Data仕様書」「コード表(xlsx)」も保存（パース定義の一次資料）

### STEP 5: 利用キーをJV-Linkに設定（疎通の前段）
- JV-Linkの設定ダイアログ（`JVSetUIProperties`）を開き、STEP3の利用キーを入力
- サンプルアプリ同梱なら、まずそれで取得できるか確認するのが確実

### STEP 6: Pythonから疎通テスト（蓄積系・最小コード）
- **32bit COMのため、取得バッチは32bit Python venvを推奨**（64bitならDllSurrogate設定が必要）
- `uv add pywin32`（取得バッチ専用環境に）
```python
import win32com.client

jv = win32com.client.Dispatch("JVDTLab.JVLink")
rc = jv.JVInit("KBARAI/1.0")          # sid（任意のアプリ識別子）
jv.JVSetUIProperties()                # 初回: ダイアログで利用キー入力

# 蓄積系の取得開始（dataspec/fromtime/optionは仕様書参照）
ret = jv.JVOpen("RACE", "20240101000000", 1)
# pywin32では [out]引数がタプルで返る: (rc, readcount, downloadcount, lasttimestamp)

while True:
    rc, buf, size, filename = jv.JVRead("", 0, "")
    if rc == 0:        # 全データ終了
        break
    if rc == -1:       # ファイル区切り → 継続
        continue
    # buf は Shift-JIS固定長 → 仕様書のバイト定義でスライスしてパース

jv.JVClose()
```
- ※ 関数シグネチャ/dataspec/戻り値は環境とSDKバージョンで差異あり。SDKサンプルと `miyamamoto/jrvltsql` の実装が一次資料。

### STEP 7: DB保存（自前パースを避ける推奨ルート）
- 車輪の再発明を避け **`miyamamoto/jrvltsql`（Apache-2.0）** を評価:
  - `git clone` → 環境変数にPostgreSQL接続情報・利用キーを設定
  - `quickstart_timeseries.bat` で初回フルセットアップ（重い・初回のみ）
  - `daily_sync.bat` 相当で日次/週次の差分同期
- これで「Windows + JV-Link → PostgreSQL」が既製機能でほぼ完結

### STEP 8: 本番連携＆自動化
1. 自宅PCのステージングDB（PostgreSQL/SQLite/DuckDB）に蓄積
2. 週1で差分を本番VPSへエクスポート/インポート（netkeibaデータとは別テーブル）
3. レースID・馬IDのマッピングテーブルでnetkeibaデータと突合
4. Windowsタスクスケジューラで週1自動実行 → 完了/失敗を既存のLINE通知と連携
   （`SCHED_JRAVAN_REMINDER_ENABLED=True` で同期前リマインダーも発火）

### リアルタイム（速報系）を使う場合の注意
- 速報オッズ/馬体重/天候馬場は `JVRTOpen`/`JVGets` でポーリング取得
- ただしJV-LinkはWindows専用 → クラウドVPSで直接は不可。リアルタイム表示には
  自宅PCの常時稼働＋VPSへの中継が必要（週1同期方針とは別の重い運用）。
  当日リアルタイムは現状のnetkeibaスクレイピングの方がクラウド向き。
