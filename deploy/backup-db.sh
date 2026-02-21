#!/bin/bash
# =============================================================
# PostgreSQL backup script (run via cron)
# Crontab: 0 3 * * 0 /opt/kbar/deploy/backup-db.sh
# =============================================================
set -e

BACKUP_DIR="/opt/kbar/backups"
KEEP_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "=== Backing up PostgreSQL ==="
docker exec kbar-postgres pg_dump -U kbar kbar | gzip > "$BACKUP_DIR/kbar_${TIMESTAMP}.sql.gz"

echo "=== Removing backups older than ${KEEP_DAYS} days ==="
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +${KEEP_DAYS} -delete

echo "Backup saved: $BACKUP_DIR/kbar_${TIMESTAMP}.sql.gz"
ls -lh "$BACKUP_DIR"/kbar_*.sql.gz | tail -5
