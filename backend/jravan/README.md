# JRA-VAN JV-Link 取得バッチ（自宅Windows PC専用）

VPS本番アプリ(Linux)とは**独立**したフォルダ。JV-Link は Windows/COM 専用のため、
データ取得はここ（自宅PC）で行い、結果だけを本番へ連携する（方式C）。

詳細・背景: `../../docs/20260609-jravan-connection.md`

## セットアップ

1. **JRA-VAN Data Lab. を契約し、利用キー(17桁)を取得**（済）
2. **JV-Link をインストール**（JRA-VAN SDK）→ COM `JVDTLab.JVLink` が登録される
3. **Python環境**（このフォルダで）
   - **32bit Python 推奨**（JV-Link は 32bit COM。64bit を使うなら DllSurrogate 設定が必要）
   - `pip install pywin32`
4. **利用キーを設定**
   ```
   copy .env.example .env
   # .env を開き JRAVAN_SERVICE_KEY=（利用キー）を記入。.env はコミットされない。
   ```

## 疎通テスト

```bash
python connect_test.py          # 初期化＋利用キー認証まで（軽量）
python connect_test.py --read   # さらにテストデータを数件読んで表示
```

- `[OK] JV-Link への接続と利用キー認証に成功しました。` が出れば接続成功。
- 失敗時は戻り値コードを JV-Data仕様書（SDK同梱）の戻り値表で確認する。
- 初回のみ `JVSetUIProperties()` ダイアログでのキー設定が必要な場合がある。

## 次のステップ（本実装）

1. `miyamamoto/jrvltsql`（Apache-2.0）を評価 → JV-Link→PostgreSQL のDB化を流用
2. 初回フルセットアップ（重い・1回）→ 日次/週次の差分同期
3. ステージングDB → 本番VPSへ差分連携、netkeibaデータと突合（レースID/馬IDマッピング）
4. Windowsタスクスケジューラで週1自動実行 + LINE同期リマインダー連携
   （`SCHED_JRAVAN_REMINDER_ENABLED=True`）
