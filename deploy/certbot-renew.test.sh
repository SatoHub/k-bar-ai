#!/bin/bash
# =============================================================
# deploy/certbot-renew.sh の wait_for_served() の回帰テスト
#
# 実行: bash deploy/certbot-renew.test.sh
#
# なぜこのテストがあるか:
#   2026-09-20、証明書の更新も nginx のリロードも成功していたのに
#   「🔴 reload したのに配信中の証明書が変わりません」を誤送信した。
#   `nginx -s reload` は非同期で、古いワーカーが既存接続を捌き終えるまで
#   メモリ上の旧証明書を返し続けるのに、reload の直後に読みに行っていたため。
#
#   当時もテストは書いていたが、`disk_notafter` を「絶対に一致しない偽の日付」に
#   差し替える作りだったため **🔴 が出るのが期待値**であり、
#   構造上このバグを検出できなかった。
#
#   → 「分岐に入ること」の検証と「分岐が正しく判定すること」の検証は別物。
#      このテストは後者（旧値を数回返した後に新値へ変わる＝実際の挙動）を検証する。
#
# 本体スクリプトから wait_for_served の定義を抜き出して評価するので、
# 関数が消えたり壊れたりすれば落ちる。
# =============================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HERE/certbot-renew.sh"

[ -r "$TARGET" ] || { echo "FAIL: $TARGET が読めない"; exit 1; }

# 本体から wait_for_served() の定義だけを抜き出す
FUNC=$(sed -n '/^wait_for_served() {/,/^}/p' "$TARGET")
if [ -z "$FUNC" ]; then
    echo "FAIL: wait_for_served() が本体スクリプトに見つからない"
    exit 1
fi

pass=0; fail=0
check() { # check <名前> <期待rc> <実rc> [補足]
    if [ "$2" = "$3" ]; then
        printf '  [OK]   %s (rc=%s) %s\n' "$1" "$3" "${4:-}"; pass=$((pass+1))
    else
        printf '  [FAIL] %s 期待rc=%s 実rc=%s %s\n' "$1" "$2" "$3" "${4:-}"; fail=$((fail+1))
    fi
}

run_case() { # run_case <WAIT_SECONDS> <stub本体> <expect値>
    local wait_s="$1" stub="$2" expect="$3"
    WAIT_SECONDS="$wait_s" bash -c "
set -uo pipefail
WAIT_SECONDS=\"\${WAIT_SECONDS}\"
STATE_FILE='$STATE'
$stub
$FUNC
out=\$(wait_for_served '$expect'); rc=\$?
printf '%s|%s' \"\$rc\" \"\$out\"
"
}

STATE=$(mktemp)
trap 'rm -f "$STATE"' EXIT

echo "wait_for_served() 回帰テスト"

# --- 1. 本命: 最初は旧証明書、数回後に新証明書に変わる（reload の実挙動） ---
#    修正前の実装はここで 1 を返して 🔴 を送っていた。0 になることを検証する。
STUB_CONVERGE='
served_notafter() {
  n=$(cat "$STATE_FILE" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$STATE_FILE"
  if [ "$n" -ge 3 ]; then printf "%s" "Sep 26 18:30:59 2026 GMT"; else printf "%s" "Sep 22 19:38:42 2026 GMT"; fi
}'
echo 0 > "$STATE"
R=$(run_case 30 "$STUB_CONVERGE" "Sep 26 18:30:59 2026 GMT")
check "3回目で新証明書に変わる → 成功と判定" 0 "${R%%|*}" "観測=${R#*|}"

# --- 2. 本当に反映されない → 不一致(1) ---
STUB_STALE='served_notafter() { printf "%s" "Sep 22 19:38:42 2026 GMT"; }'
R=$(run_case 4 "$STUB_STALE" "Sep 26 18:30:59 2026 GMT")
check "旧証明書のまま → 不一致と判定" 1 "${R%%|*}"

# --- 3. TLS に到達できない → 観測不能(2)。不一致と区別すること ---
STUB_EMPTY='served_notafter() { printf "%s" ""; }'
R=$(run_case 4 "$STUB_EMPTY" "Sep 26 18:30:59 2026 GMT")
check "TLS応答なし → 観測不能と判定(不一致と区別)" 2 "${R%%|*}"

# --- 4. 即一致 ---
STUB_OK='served_notafter() { printf "%s" "Sep 26 18:30:59 2026 GMT"; }'
R=$(run_case 30 "$STUB_OK" "Sep 26 18:30:59 2026 GMT")
check "最初から一致 → 即成功" 0 "${R%%|*}"

# --- 5. 実時間で打ち切る（回数ではなく壁時計）---
#    プローブが毎回ストールしても WAIT_SECONDS + プローブ1回分で収まること。
STUB_SLOW='served_notafter() { sleep 3; printf "%s" "Sep 22 19:38:42 2026 GMT"; }'
t0=$(date +%s)
R=$(run_case 6 "$STUB_SLOW" "Sep 26 18:30:59 2026 GMT")
elapsed=$(( $(date +%s) - t0 ))
check "プローブがストールしても実時間で打ち切る" 1 "${R%%|*}" "所要=${elapsed}秒"
if [ "$elapsed" -le 15 ]; then
    printf '  [OK]   打ち切りが壁時計基準 (%s秒 <= 15秒)\n' "$elapsed"; pass=$((pass+1))
else
    printf '  [FAIL] 打ち切りが回数基準になっている疑い (%s秒 > 15秒)\n' "$elapsed"; fail=$((fail+1))
fi

echo "合計: $((pass+fail)) 件中 $pass 件 pass / $fail 件 fail"
[ "$fail" -eq 0 ] || exit 1
echo "すべて期待通り。"
