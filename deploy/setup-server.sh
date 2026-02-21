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

echo "=== 7. Install certbot + apache2-utils (for htpasswd) ==="
apt-get install -y certbot apache2-utils

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Next steps:"
echo "    1. ssh deploy@YOUR_IP"
echo "    2. Clone repo to /opt/kbar"
echo "    3. Copy .env.production to /opt/kbar/.env"
echo "    4. Create Basic auth password:"
echo "       htpasswd -c /opt/kbar/docker/nginx/.htpasswd admin"
echo "    5. Run: bash deploy/deploy.sh"
echo "============================================"
