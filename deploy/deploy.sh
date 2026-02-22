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

echo "=== 3. Build & start containers ==="
docker compose --env-file .env -f docker/docker-compose.prod.yml build --no-cache
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d

echo "=== 4. Wait for services ==="
sleep 10

echo "=== 5. Health check ==="
if curl -sf http://localhost/api/v1/health > /dev/null 2>&1; then
    echo "Backend: OK"
else
    echo "Backend: FAILED (check logs: docker compose --env-file .env -f docker/docker-compose.prod.yml logs backend)"
fi

if curl -sf http://localhost/ > /dev/null 2>&1; then
    echo "Frontend: OK"
else
    echo "Frontend: FAILED (check logs: docker compose --env-file .env -f docker/docker-compose.prod.yml logs frontend)"
fi

echo ""
echo "=== Deploy complete ==="
echo "Useful commands:"
echo "  Logs:    docker compose --env-file .env -f docker/docker-compose.prod.yml logs -f"
echo "  Stop:    docker compose --env-file .env -f docker/docker-compose.prod.yml down"
echo "  Restart: docker compose --env-file .env -f docker/docker-compose.prod.yml restart"
