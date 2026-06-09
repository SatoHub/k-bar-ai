"""JRA-VAN JV-Link 疎通テストスクリプト（自宅Windows PC専用）.

JV-Link への接続〜（利用キー認証）〜実データ取得までを段階的に確認する。
利用キーは「JV-Link設定」で登録済みであることを前提とし、スクリプトからの
JVSetServiceKey は best-effort（失敗しても登録済みキーで続行）とする。

前提:
  - Windows PC に JV-Link がインストール済み（COM: JVDTLab.JVLink）
  - 「JV-Link設定」で利用キー登録済み
  - 32bit Python + pywin32

使い方:
  python connect_test.py            # 接続＋実データ取得を検証
  python connect_test.py --read     # 取得レコードを多めに表示

詳細手順: docs/20260609-jravan-connection.md
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Windowsコンソールの文字化け対策（UTF-8で出力）
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

SOFTWARE_ID = "KBARAI/0.1"        # JVInit に渡すソフト識別子（個人利用は任意）
TEST_DATASPEC = "RACE"            # 取得データ種別
TEST_OPTION = 2                   # 1=通常 2=今週分(軽い) 3=ダイアログ無し 4=セットアップ(重い)
FROM_DAYS_AGO = 7                 # 取得開始 = 今日からこの日数前（軽量化のため直近のみ）
MAX_RECORDS = 5                   # 通常時に表示するレコード数（--read で20件）
BUFFER_SIZE = 120000              # JVRead 用バッファ容量（0だとアクセス違反で落ちる）


def load_service_key() -> str:
    """同フォルダの .env もしくは環境変数から利用キーを読み込む。"""
    import os

    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.environ.get("JRAVAN_SERVICE_KEY", "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="JRA-VAN JV-Link 疎通テスト")
    parser.add_argument("--read", action="store_true", help="取得レコードを多めに表示")
    args = parser.parse_args()
    max_records = 20 if args.read else MAX_RECORDS

    key = load_service_key()
    masked = f"{key[:4]}-****-****-****-{key[-1:]}" if key else "(未設定)"
    print(f"[1/5] 利用キー読込: {masked}")

    try:
        import win32com.client  # type: ignore
    except ImportError:
        sys.exit("[ERROR] pywin32 がありません。`pip install pywin32`（Windows専用）。")

    try:
        jv = win32com.client.Dispatch("JVDTLab.JVLink")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[ERROR] JV-Link(COM) を生成できません: {e}")

    # --- 初期化 ---
    rc = jv.JVInit(SOFTWARE_ID)
    print(f"[2/5] JVInit -> {rc}")
    if rc != 0:
        sys.exit(f"[ERROR] JVInit 失敗 (code={rc})")

    # --- 利用キー認証（best-effort: 失敗しても登録済みキーで続行） ---
    if key:
        rc = jv.JVSetServiceKey(key)
        if rc == 0:
            print(f"[3/5] JVSetServiceKey -> 0 (キー再設定OK)")
        else:
            print(f"[3/5] JVSetServiceKey -> {rc} (警告: 「JV-Link設定」で登録済みのキーを使用して続行)")
    else:
        print("[3/5] JVSetServiceKey -> skip (.env未設定。登録済みキーを使用)")

    # --- 実データ取得で検証（これが本当の疎通確認） ---
    fromtime = (datetime.now() - timedelta(days=FROM_DAYS_AGO)).strftime("%Y%m%d000000")
    print(f"[4/5] JVOpen(dataspec={TEST_DATASPEC}, from={fromtime}, option={TEST_OPTION}) ...")
    open_ret = jv.JVOpen(TEST_DATASPEC, fromtime, TEST_OPTION)
    if isinstance(open_ret, (tuple, list)):
        rc = open_ret[0]
        readcount = open_ret[1] if len(open_ret) > 1 else "?"
        downloadcount = open_ret[2] if len(open_ret) > 2 else "?"
        print(f"      JVOpen -> rc={rc}, readcount={readcount}, downloadcount={downloadcount}")
    else:
        rc = open_ret
        print(f"      JVOpen -> {rc}")

    if rc != 0:
        # 認証系エラー(-301/-302/-303)ならキー/契約の問題
        sys.exit(
            f"[ERROR] JVOpen 失敗 (code={rc})。\n"
            "        -301/-302/-303 は利用キー・契約の認証エラー。"
            "それ以外はJV-Data仕様書の戻り値表を参照。"
        )

    print("[OK] JV-Link への接続・認証に成功しました（JVOpen rc=0）。")

    # --- 数件読み込んで中身を確認 ---
    print(f"[5/5] データ読込（最大{max_records}件）...")
    shown = 0
    wait_count = 0
    while shown < max_records:
        read_rc, buf, size, filename = jv.JVRead("", BUFFER_SIZE, "")
        if read_rc == 0:
            print("      （全データ読み込み完了）")
            break
        if read_rc == -1:
            continue  # ファイル区切り
        if read_rc == -3:
            wait_count += 1
            if wait_count > 60:
                print("      （ダウンロード待ちが長いため打ち切り。接続自体は成功）")
                break
            time.sleep(0.5)
            continue
        if read_rc < 0:
            print(f"      [WARN] JVRead code={read_rc}")
            break
        rec_type = buf[:2] if isinstance(buf, str) else "?"
        head = (buf[:50] if isinstance(buf, str) else str(buf)[:50])
        print(f"      rec#{shown + 1} type={rec_type} ({read_rc}B) {head}")
        shown += 1

    jv.JVClose()
    print(f"\n[DONE] 疎通テスト完了。{shown}件のレコードを取得・表示しました。")
    if shown == 0:
        print("       （直近7日に該当データが無い可能性。接続自体は成功しています）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
