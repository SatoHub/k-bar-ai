"""JRA-VAN JV-Link 疎通テストスクリプト（自宅Windows PC専用）.

利用キーを .env から読み込み、JV-Link への接続〜認証〜（任意で）データ取得までを
段階的に確認する。VPS本番アプリ(Linux)とは独立しており、ここだけ pywin32 に依存する。

前提:
  - Windows PC に JV-Link がインストール済み（COM: JVDTLab.JVLink が登録済み）
  - 32bit Python 推奨（JV-Link は 32bit COM。64bit なら DllSurrogate 設定が必要）
  - `pip install pywin32`
  - 同フォルダの .env に JRAVAN_SERVICE_KEY を設定（.env.example をコピー）

使い方:
  python connect_test.py            # 初期化＋利用キー認証まで（軽量・推奨）
  python connect_test.py --read     # さらに今週分のレースデータを数件読んで表示

詳細手順: docs/20260609-jravan-connection.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# JVInit に渡すソフト識別子(sid)。開発・個人利用では任意の文字列で可。
SOFTWARE_ID = "KBARAI/0.1"

# 疎通用に取得するデータ種別(dataspec)と取得開始日時(fromtime)。
# "RACE" = レース詳細。option=2 は「通常データ（今週分中心）」で軽め。
TEST_DATASPEC = "RACE"
TEST_FROMTIME = "20240101000000"  # YYYYMMDDhhmmss
TEST_OPTION = 2  # 1=セットアップ(重い) / 2=通常データ / 3=ダイアログなし通常
MAX_RECORDS = 5  # --read 時に表示する最大レコード数


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

    key = os.environ.get("JRAVAN_SERVICE_KEY", "").strip()
    if not key:
        sys.exit(
            "[ERROR] JRAVAN_SERVICE_KEY が未設定です。"
            " .env.example をコピーして .env を作り、利用キーを記入してください。"
        )
    return key


def main() -> int:
    parser = argparse.ArgumentParser(description="JRA-VAN JV-Link 疎通テスト")
    parser.add_argument(
        "--read", action="store_true",
        help="認証後、テストデータを数件読み込んで表示する",
    )
    args = parser.parse_args()

    key = load_service_key()
    masked = f"{key[:4]}-****-****-****-{key[-1:]}"
    print(f"[1/4] 利用キー読込: {masked}")

    try:
        import win32com.client  # type: ignore
    except ImportError:
        sys.exit(
            "[ERROR] pywin32 が見つかりません。`pip install pywin32` を実行してください"
            "（このスクリプトは Windows でのみ動作します）。"
        )

    # --- JV-Link 初期化 ---
    try:
        jv = win32com.client.Dispatch("JVDTLab.JVLink")
    except Exception as e:  # noqa: BLE001
        sys.exit(
            f"[ERROR] JV-Link(COM: JVDTLab.JVLink) を生成できません: {e}\n"
            "        JV-Link がインストールされているか、"
            "32bit/64bit の組み合わせ（DllSurrogate）を確認してください。"
        )

    rc = jv.JVInit(SOFTWARE_ID)
    print(f"[2/4] JVInit -> {rc}")
    if rc != 0:
        sys.exit(f"[ERROR] JVInit 失敗 (code={rc})。JV-Data仕様書の戻り値表を参照。")

    # --- 利用キー認証 ---
    rc = jv.JVSetServiceKey(key)
    print(f"[3/4] JVSetServiceKey -> {rc}")
    if rc != 0:
        sys.exit(
            f"[ERROR] 利用キー認証に失敗 (code={rc})。\n"
            "        キーの誤り/期限切れ、または初回はJVSetUIProperties()のダイアログ"
            "での設定が必要な場合があります。"
        )

    print("[OK] JV-Link への接続と利用キー認証に成功しました。")

    if not args.read:
        print("\nヒント: 実データ取得も試すには `python connect_test.py --read`")
        jv.JVClose()
        return 0

    # --- 任意: テストデータ取得 ---
    print(f"[4/4] JVOpen(dataspec={TEST_DATASPEC}, option={TEST_OPTION}) ...")
    open_rc = jv.JVOpen(TEST_DATASPEC, TEST_FROMTIME, TEST_OPTION)
    # pywin32 では [out] 引数がタプルで返る環境がある: (rc, readcount, downloadcount, ts)
    if isinstance(open_rc, (tuple, list)):
        rc = open_rc[0]
        print(f"      JVOpen -> rc={rc}, readcount={open_rc[1]}, downloadcount={open_rc[2]}")
    else:
        rc = open_rc
        print(f"      JVOpen -> {rc}")
    if rc != 0:
        sys.exit(f"[ERROR] JVOpen 失敗 (code={rc})。")

    shown = 0
    while shown < MAX_RECORDS:
        read_rc, buf, size, filename = jv.JVRead("", 0, "")
        if read_rc == 0:
            print("      （全データ読み込み完了）")
            break
        if read_rc == -1:
            # ファイル区切り。継続。
            continue
        if read_rc == -3:
            print("      （ダウンロード中… JVStatus待ち）")
            continue
        if read_rc < 0:
            print(f"      [WARN] JVRead エラー code={read_rc}")
            break
        # read_rc > 0: 読み込んだバイト数。buf は Shift-JIS固定長。
        head = buf[:40] if isinstance(buf, str) else str(buf)[:40]
        print(f"      rec#{shown + 1} ({read_rc}B) {head}...")
        shown += 1

    jv.JVClose()
    print("\n[DONE] 疎通テスト完了。固定長パースは JV-Data仕様書 / jrvltsql を参照。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
