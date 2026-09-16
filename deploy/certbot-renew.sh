#!/bin/bash
# =============================================================
# Let's Encrypt IPアドレス証明書(shortlived / 有効期間160時間)の更新
#
# systemd timer (kbar-certbot-renew.timer) から8時間ごとに実行される。
# 有効期間が短いため「更新が静かに止まる」ことが最大のリスク。そこで:
#
#   1. certbot renew を実行する
#   2. **ディスク上の証明書と443で配信中の証明書の期限を比較**し、
#      違っていれば無条件に nginx を reload する
#      (certbot の出力文字列に依存しないので、文言が変わっても壊れない。
#       かつ「ファイルは新しいが配信は古い」事故を自動で復旧できる)
#   3. 残り時間が閾値を切っていたら通知する(更新自体が回っていない事故の検知)
#
# 通知は backend コンテナ内の NotificationService を使い、それが使えない場合は
# deploy/line-notify.sh (curl 直叩き) にフォールバックする。
# スクリプト自体が異常終了した場合は systemd の OnFailure= が拾う。
#
# 手動実行: bash /opt/kbar/deploy/certbot-renew.sh
# ログ確認: journalctl -t kbar-certbot --since today
# 詳細:     docs/20260916-https-ip-certificate.md
# =============================================================
# -e は使わない: 失敗時に通知してから終了したいため自前でハンドリングする
set -uo pipefail

PROJECT_DIR=/opt/kbar
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"
FALLBACK_NOTIFY="$PROJECT_DIR/deploy/line-notify.sh"
TAG=kbar-certbot
NGINX_CONTAINER=kbar-nginx
BACKEND_CONTAINER=kbar-backend
CERT_NAME=kbar
LIVE_CERT="/etc/letsencrypt/live/${CERT_NAME}/fullchain.pem"

# 残りがこの時間を切っていたら警告する。
# certbot は有効期間10日以下の証明書を「残り1/2(=80時間)」で更新する。
# ただし ARI(ACME Renewal Information)由来の窓が使われると更新が
# もっと遅くなる可能性があるため、正常動作で鳴らないよう余裕を取って 24 にしている。
# 「いつも鳴っている通知」になると本当の停止を見逃すため、ここは低めが正しい。
# 動作確認用に上書きできる: WARN_HOURS=200 bash deploy/certbot-renew.sh
WARN_HOURS="${WARN_HOURS:-24}"

# echo は certbot 出力が -n / -e で始まるとオプションとして食うため使わない
log() { printf '%s\n' "$*" | logger -t "$TAG"; }

compose() {
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

# LINE通知。backend コンテナ経由 → 失敗したら curl 直叩きにフォールバックする。
# 通知自体が失敗しても更新処理は止めない(ログには必ず残す)。
notify() {
    local msg="$1"
    log "notify: $msg"

    if docker exec -e KBAR_NOTIFY_MSG="$msg" -i "$BACKEND_CONTAINER" \
        uv run --no-dev --frozen python - <<'PY' 2>&1 | logger -t "$TAG"
import asyncio
import os
import sys

from app.services.notification_service import get_notification_service


async def main() -> int:
    svc = get_notification_service()
    if not svc.is_configured:
        print("LINE not configured", file=sys.stderr)
        return 1
    ok = await svc.push_text(os.environ["KBAR_NOTIFY_MSG"])
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
PY
    then
        return 0
    fi

    # backend コンテナが落ちている / Docker ごと死んでいる場合はここに来る。
    # まさに通知が必要な局面なので、コンテナに依存しない経路で再送する。
    log "WARNING: backend 経由の通知に失敗。line-notify.sh にフォールバックする"
    if [ -x "$FALLBACK_NOTIFY" ] || [ -r "$FALLBACK_NOTIFY" ]; then
        bash "$FALLBACK_NOTIFY" "$msg" || log "ERROR: フォールバック通知も失敗した"
    else
        log "ERROR: $FALLBACK_NOTIFY が無く通知できない"
    fi
}

# 443 で実際に配信されている証明書の notAfter を取る
served_notafter() {
    echo | timeout 15 openssl s_client -connect 127.0.0.1:443 2>/dev/null \
        | openssl x509 -enddate -noout 2>/dev/null | cut -d= -f2
}

# ディスク上(certbot が書いた)証明書の notAfter を取る
disk_notafter() {
    compose run --rm -T --entrypoint openssl certbot \
        x509 -enddate -noout -in "$LIVE_CERT" 2>/dev/null | cut -d= -f2
}

reload_nginx() {
    if docker exec "$NGINX_CONTAINER" nginx -t >/dev/null 2>&1 \
        && docker exec "$NGINX_CONTAINER" nginx -s reload >/dev/null 2>&1; then
        log "nginx reload 成功"
        return 0
    fi
    return 1
}

log "=== certbot renew 開始 ==="

OUT=$(compose run --rm -T certbot renew 2>&1)
RC=$?
log "$OUT"

# --- 配信内容とディスク内容を比較して、必要なら reload する ---
# certbot renew が部分的に失敗していても(複数 lineage がある場合など)、
# kbar が更新されていれば配信に反映したいので RC 判定より先に行う。
DISK_END=$(disk_notafter)
SERVED_END=$(served_notafter)
log "ディスク上: ${DISK_END:-取得不可} / 配信中: ${SERVED_END:-取得不可}"

if [ -n "$DISK_END" ] && [ -n "$SERVED_END" ] && [ "$DISK_END" != "$SERVED_END" ]; then
    log "配信中の証明書がディスク上と異なる。reload する。"
    if reload_nginx; then
        SERVED_END=$(served_notafter)
        if [ "$DISK_END" = "$SERVED_END" ]; then
            notify "✅ K-Bar AI: HTTPS証明書を更新しました(期限 $SERVED_END)。"
        else
            notify "🔴 K-Bar AI: reload したのに配信中の証明書が変わりません(ディスク $DISK_END / 配信 ${SERVED_END:-取得不可})。至急確認してください。"
        fi
    else
        notify "🔴 K-Bar AI: 証明書は更新できましたが nginx のリロードに失敗しました。古い証明書が配信され続けます。至急確認してください。"
    fi
fi

# --- certbot 自体の失敗を通知する(reload 試行の後) ---
if [ "$RC" -ne 0 ]; then
    notify "🔴 K-Bar AI: HTTPS証明書の更新に失敗しました (exit=$RC)。証明書は160時間で失効するため数日でHTTPSが停止します。VPSで journalctl -t $TAG --since today を確認してください。"
    exit 1
fi

# --- 安全網: 配信中の証明書の残り時間を検査する ---
if [ -z "$SERVED_END" ]; then
    notify "🔴 K-Bar AI: 443で配信されている証明書を読み取れません。HTTPSが停止している可能性があります。"
    exit 1
fi

END_EPOCH=$(date -d "$SERVED_END" +%s 2>/dev/null)
if [ -z "$END_EPOCH" ]; then
    # ここを黙って通すと3段目の安全網が消えたことに誰も気づけない
    notify "🔴 K-Bar AI: 証明書の期限を解析できませんでした($SERVED_END)。更新監視が機能していません。"
    exit 1
fi

LEFT_HOURS=$(( (END_EPOCH - $(date +%s)) / 3600 ))
log "配信中の証明書: 残り ${LEFT_HOURS} 時間 (期限 $SERVED_END)"

if [ "$LEFT_HOURS" -lt "$WARN_HOURS" ]; then
    notify "⚠️ K-Bar AI: HTTPS証明書の残りが ${LEFT_HOURS} 時間です(期限 $SERVED_END)。自動更新が回っていない可能性があります。journalctl -t $TAG を確認してください。"
fi

log "=== certbot renew 完了 ==="
