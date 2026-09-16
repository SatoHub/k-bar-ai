#!/bin/bash
# =============================================================
# ConoHa VPS Initial Setup Script
# Run as root on a fresh Ubuntu 24.04 server
# Usage: ssh root@YOUR_IP 'bash -s' < deploy/setup-server.sh
# =============================================================
set -e

echo "=== 1. System update ==="
apt-get update && apt-get upgrade -y

echo "=== 2. Install Docker ==="
curl -fsSL https://get.docker.com | sh

echo "=== 3. Create deploy user ==="
if ! id "deploy" &>/dev/null; then
    useradd -m -s /bin/bash -G docker deploy
    echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/ 2>/dev/null || true
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    echo "User 'deploy' created. SSH key copied from root."
else
    echo "User 'deploy' already exists."
fi

echo "=== 4. Install Docker Compose plugin ==="
apt-get install -y docker-compose-plugin

echo "=== 5. Setup firewall ==="
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "=== 6. Create app directory ==="
mkdir -p /opt/kbar
chown deploy:deploy /opt/kbar

echo "=== 7. Install apache2-utils (for htpasswd) ==="
# certbot は apt 版を入れない。
# Ubuntu 24.04 の apt 版は 2.9.0 で、IPアドレス証明書の webroot 対応(5.4以上)を
# 満たさない。さらに apt 版が入れる certbot.timer が /usr/bin/certbot を呼ぶため、
# 5.x が書いた renewal 設定(preferred_profile = shortlived)を解釈できず
# 更新が静かに失敗する。証明書は compose の certbot サービス
# (certbot/certbot:v5.8.0) を使う。詳細は docs/20260916-https-ip-certificate.md
apt-get install -y apache2-utils

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Next steps:"
echo "    1. ssh deploy@YOUR_IP"
echo "    2. Clone repo to /opt/kbar"
echo "    3. Copy .env.production to /opt/kbar/.env"
echo "    4. Create Basic auth password:"
echo "       htpasswd -c /opt/kbar/docker/nginx/.htpasswd admin"
echo ""
echo "    5. HTTPS のブートストラップ（証明書が無い状態では nginx が起動できないため"
echo "       この順序でしか立ち上がらない。詳細は docs/20260916-https-ip-certificate.md）:"
echo "       a) echo 'NGINX_CONF=./nginx/nginx.bootstrap.conf' >> /opt/kbar/.env"
echo "       b) bash deploy/deploy.sh          # TLS なしで起動する"
echo "       c) cd /opt/kbar && docker compose --env-file .env \\"
echo "            -f docker/docker-compose.prod.yml run --rm certbot certonly \\"
echo "            --non-interactive --agree-tos --register-unsafely-without-email \\"
echo "            --preferred-profile shortlived --webroot -w /var/www/certbot \\"
echo "            --ip-address YOUR_IP --cert-name kbar"
echo "       d) .env から NGINX_CONF の行を削除する"
echo "       e) bash deploy/deploy.sh          # 本番設定(TLS あり)で再作成される"
echo "============================================"
