#!/bin/bash
# VPSデプロイ後のヘルスチェックスクリプト
# 使い方: ssh user@vps 'bash -s' < deploy/health-check.sh

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "  ${GREEN}[OK]${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}[NG]${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN++)); }

echo "========================================="
echo " K-Bar AI ヘルスチェック"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# --- 1. スケジューラジョブ登録確認 ---
echo "1. スケジューラジョブ登録"
JOB_LOG=$(docker logs kbar-backend 2>&1 | grep "Registered" | tail -1)
if echo "$JOB_LOG" | grep -q "Registered 8"; then
    pass "8ジョブ登録済み"
elif echo "$JOB_LOG" | grep -q "Registered"; then
    fail "ジョブ数が不正: $JOB_LOG"
else
    fail "ジョブ登録ログが見つかりません"
fi
echo ""

# --- 2. メモリ制限確認 ---
echo "2. メモリ制限（mem_limit）"
for svc in kbar-postgres kbar-backend kbar-frontend kbar-nginx; do
    LIMIT=$(docker inspect "$svc" --format '{{.HostConfig.Memory}}' 2>/dev/null || echo "0")
    if [ "$LIMIT" = "0" ] || [ -z "$LIMIT" ]; then
        fail "$svc: メモリ制限なし"
    else
        LIMIT_MB=$((LIMIT / 1024 / 1024))
        pass "$svc: ${LIMIT_MB}MB 制限"
    fi
done
echo ""

# --- 3. メモリ使用量確認 ---
echo "3. メモリ使用量"
docker stats --no-stream --format "  {{.Name}}: {{.MemUsage}} ({{.MemPerc}})" 2>/dev/null || warn "docker stats取得失敗"
echo ""

# --- 4. ワーカー数確認 ---
echo "4. Uvicornワーカー数"
WORKER_COUNT=$(docker logs kbar-backend 2>&1 | grep -c "Started server process" || true)
if [ "$WORKER_COUNT" -eq 1 ]; then
    pass "ワーカー1つ（正常）"
elif [ "$WORKER_COUNT" -eq 0 ]; then
    warn "ワーカー起動ログが見つかりません（起動直後の場合は正常）"
else
    fail "ワーカー${WORKER_COUNT}つ（1つであるべき）"
fi
echo ""

# --- 5. Chromiumフラグ確認 ---
echo "5. Chromiumフラグ"
BROWSER_LOG=$(docker logs kbar-backend 2>&1 | grep "Browser launched" | tail -1)
BROWSER_ERR=$(docker logs kbar-backend 2>&1 | grep -i "browser.*error\|chromium.*crash\|out of memory" | tail -1)
if [ -n "$BROWSER_ERR" ]; then
    fail "ブラウザエラー検出: $BROWSER_ERR"
elif [ -n "$BROWSER_LOG" ]; then
    pass "ブラウザ起動成功: $BROWSER_LOG"
else
    warn "ブラウザ起動ログなし（まだスクレイピング未実行）"
fi
echo ""

# --- 6. 朝ジョブ確認 ---
echo "6. 出馬表ジョブ実行状況"
SHUTUBA_LOG=$(docker logs kbar-backend 2>&1 | grep "Shutuba fetch" | tail -3)
if [ -n "$SHUTUBA_LOG" ]; then
    echo "$SHUTUBA_LOG" | while IFS= read -r line; do
        if echo "$line" | grep -q "complete"; then
            pass "$line"
        elif echo "$line" | grep -q "starting"; then
            pass "$line"
        elif echo "$line" | grep -q "failed"; then
            fail "$line"
        fi
    done
    # Verification log
    VERIFY_LOG=$(docker logs kbar-backend 2>&1 | grep "Shutuba verification" | tail -1)
    if echo "$VERIFY_LOG" | grep -q "still without"; then
        warn "$VERIFY_LOG"
    elif [ -n "$VERIFY_LOG" ]; then
        pass "$VERIFY_LOG"
    fi
else
    warn "出馬表ジョブ未実行（9:00 or 18:00 JST以降に再確認）"
fi
echo ""

# --- 7. ホストメモリ確認 ---
echo "7. ホストメモリ"
TOTAL_MEM=$(free -m | awk '/^Mem:/ {print $2}')
USED_MEM=$(free -m | awk '/^Mem:/ {print $3}')
USAGE_PCT=$((USED_MEM * 100 / TOTAL_MEM))
if [ "$TOTAL_MEM" -ge 1900 ]; then
    pass "合計: ${TOTAL_MEM}MB（2GB以上）"
else
    warn "合計: ${TOTAL_MEM}MB（2GB未満 — 増設を推奨）"
fi
if [ "$USAGE_PCT" -le 80 ]; then
    pass "使用率: ${USAGE_PCT}%（${USED_MEM}MB / ${TOTAL_MEM}MB）"
else
    warn "使用率: ${USAGE_PCT}%（${USED_MEM}MB / ${TOTAL_MEM}MB）— 高負荷"
fi
echo ""

# --- サマリー ---
echo "========================================="
echo -e " 結果: ${GREEN}OK=${PASS}${NC}  ${RED}NG=${FAIL}${NC}  ${YELLOW}WARN=${WARN}${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e " ${GREEN}全チェック通過${NC}"
else
    echo -e " ${RED}${FAIL}件の問題あり — 上記を確認してください${NC}"
fi
echo "========================================="
