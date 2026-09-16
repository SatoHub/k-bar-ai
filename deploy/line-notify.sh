#!/bin/bash
# =============================================================
# LINE へ1通テキストを送る（コンテナに依存しない経路）
#
# 使い方: bash /opt/kbar/deploy/line-notify.sh "メッセージ"
#
# なぜ存在するか:
#   通常の通知は backend コンテナ内の NotificationService を使う
#   (deploy/certbot-renew.sh の notify())。しかし Docker デーモン停止や
#   backend コンテナ落ちという「まさに知りたい障害」では、その経路自体が死ぬ。
#   このスクリプトは curl と python3 だけで動くので、その場合でも通知できる。
#
# 資格情報は /opt/kbar/.env から読む(gitignore 済み)。
# アクセストークンを argv に出さないため、curl の設定は stdin 経由で渡し、
# 本文は 600 の一時ファイル経由で渡す。
# =============================================================
set -uo pipefail

ENV_FILE="${ENV_FILE:-/opt/kbar/.env}"
TAG=kbar-line-notify

log() { echo "$*" | logger -t "$TAG"; }

MSG="${1:-}"
if [ -z "$MSG" ]; then
    log "ERROR: メッセージが空"
    exit 2
fi

if [ ! -r "$ENV_FILE" ]; then
    log "ERROR: $ENV_FILE が読めない"
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

TOKEN="${LINE_CHANNEL_ACCESS_TOKEN:-}"
USER_ID="${LINE_USER_ID:-}"
if [ -z "$TOKEN" ] || [ -z "$USER_ID" ]; then
    log "ERROR: LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定"
    exit 1
fi

TMP=$(mktemp) || { log "ERROR: 一時ファイルを作れない"; exit 1; }
chmod 600 "$TMP"
trap 'rm -f "$TMP"' EXIT

# JSON は python3 で組む(手組みするとメッセージ内の引用符で壊れる)
if ! MSG="$MSG" USER_ID="$USER_ID" python3 -c '
import json, os, sys
json.dump({
    "to": os.environ["USER_ID"],
    "messages": [{"type": "text", "text": os.environ["MSG"][:4900]}],
}, sys.stdout)
' > "$TMP"; then
    log "ERROR: JSON 生成に失敗"
    exit 1
fi

# トークンを argv に出さないため、url/header/method は stdin の設定で渡す。
# 本文は --data @file で渡す(argv にも設定にも中身が出ない)。
HTTP_CODE=$(curl --silent --show-error --max-time 30 \
    --output /dev/null --write-out '%{http_code}' \
    --data "@$TMP" \
    --config - <<CURLCFG
url = "https://api.line.me/v2/bot/message/push"
request = "POST"
header = "Authorization: Bearer ${TOKEN}"
header = "Content-Type: application/json"
CURLCFG
) || { log "ERROR: curl の実行に失敗"; exit 1; }

if [ "$HTTP_CODE" = "200" ]; then
    log "送信成功: ${MSG:0:80}"
    exit 0
fi

log "ERROR: LINE API が $HTTP_CODE を返した"
exit 1
