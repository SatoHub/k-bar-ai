#!/bin/bash
# =============================================================
# Deploy K-Bar AI to production
# Run from the project root on the VPS: bash deploy/deploy.sh
# =============================================================
set -e

PROJECT_DIR="/opt/kbar"
cd "$PROJECT_DIR"

echo "=== 1. Pull latest code ==="
git pull origin master

echo "=== 2. Check .env ==="
if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.production.example to .env and fill in values."
    exit 1
fi

echo "=== 3. Install certificate renewal timer ==="
# 160時間証明書なので、この timer が無いと約6.7日で HTTPS が停止する。
# 冪等なので毎回実行してよい(unit 消失やサーバー再構築からの自己回復も兼ねる)。
sudo install -m 644 deploy/systemd/kbar-certbot-renew.service /etc/systemd/system/
sudo install -m 644 deploy/systemd/kbar-certbot-renew.timer /etc/systemd/system/
sudo install -m 644 deploy/systemd/kbar-certbot-renew-failed.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kbar-certbot-renew.timer

echo "=== 4. Build & start containers ==="
docker compose --env-file .env -f docker/docker-compose.prod.yml build --no-cache
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d

echo "=== 5. Apply nginx config ==="
# nginx.conf は bind mount なので、内容だけ変わった場合 up -d では
# コンテナが再作成されず新しい設定が読み込まれない(＝設定変更したつもりで
# 旧設定のまま動き続ける)。明示的に検証してリロードする。
if docker exec kbar-nginx nginx -t; then
    docker exec kbar-nginx nginx -s reload
    echo "nginx: config reloaded"
else
    echo "nginx: CONFIG TEST FAILED — 旧設定のまま動作中。設定を修正すること" >&2
fi

echo "=== 6. Wait for services ==="
sleep 10

echo "=== 7. Health check ==="
# ⚠️ nginx 越しに `curl -sf http://localhost/...` を使ってはいけない。
# 80番は HTTPS へのリダイレクトを返すため、-L の無い curl -f は 3xx を
# 成功扱いにし、backend/frontend が全滅していても OK と報告してしまう。
# また 443 も Basic 認証が proxy_pass より前に評価されるので、401 は
# 「nginx が生きている」ことしか示さない。upstream はコンテナ内から直接叩く。
if docker exec kbar-backend curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "Backend: OK"
else
    echo "Backend: FAILED (check logs: docker compose --env-file .env -f docker/docker-compose.prod.yml logs backend)"
fi

# frontend は node:22-alpine で curl が無いため busybox wget を使う
if docker exec kbar-frontend wget -q -O /dev/null http://localhost:3000/ 2>/dev/null; then
    echo "Frontend: OK"
else
    echo "Frontend: FAILED (check logs: docker compose --env-file .env -f docker/docker-compose.prod.yml logs frontend)"
fi

# nginx が TLS を終端できているか(証明書を読めているか)を確認する
if echo | timeout 15 openssl s_client -connect 127.0.0.1:443 2>/dev/null | grep -q "BEGIN CERTIFICATE"; then
    CERT_END=$(echo | timeout 15 openssl s_client -connect 127.0.0.1:443 2>/dev/null | openssl x509 -enddate -noout | cut -d= -f2)
    echo "HTTPS: OK (証明書の期限 $CERT_END)"
else
    echo "HTTPS: FAILED — 443で証明書を配信できていない。証明書が未取得なら .env に" >&2
    echo "  NGINX_CONF=./nginx/nginx.bootstrap.conf を置いて取得手順を実施すること" >&2
fi

# 80番がリダイレクトを返しているか(平文で本体を配信していないか)
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 http://localhost/ 2>/dev/null)
if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "301" ]; then
    echo "HTTP redirect: OK ($HTTP_CODE)"
else
    echo "HTTP redirect: 想定外の応答 $HTTP_CODE (平文配信になっていないか確認すること)" >&2
fi

echo ""
echo "=== Deploy complete ==="
echo "Useful commands:"
echo "  Logs:    docker compose --env-file .env -f docker/docker-compose.prod.yml logs -f"
echo "  Stop:    docker compose --env-file .env -f docker/docker-compose.prod.yml down"
echo "  Restart: docker compose --env-file .env -f docker/docker-compose.prod.yml restart"
