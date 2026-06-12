#!/usr/bin/env bash
# sync_pedigree_to_vps.sh
# 自宅PC専用: アプリDB kbar の horse_pedigree（血統・自己完結テーブル）を
# 本番VPSへデータ同期する。スキーマは alembic マイグレーションでVPS側に
# 既に作成済みである前提（master push → デプロイ時に自動適用）。
#
# 流れ:
#   1. ローカル kbar-postgres から horse_pedigree を data-only で pg_dump
#   2. scp でVPSへ転送
#   3. VPS側で TRUNCATE → COPY ロード（VPSの /opt/kbar/.env から DB認証を読む）
#
# 使い方:  bash backend/jravan/sync_pedigree_to_vps.sh
# 前提:    ローカルでテーブルが populate 済み（populate_horse_pedigree.sql 実行後）
#
# UMセットアップでカバレッジを増やした後も、本スクリプト再実行で本番へ反映できる。
set -euo pipefail

VPS_HOST="root@133.117.72.213"
VPS_KEY="$HOME/.ssh/key-2026-02-21-22-04.pem"
LOCAL_CT="kbar-postgres"
DUMP_LOCAL="/tmp/horse_pedigree_dump.sql"
DUMP_REMOTE="/tmp/horse_pedigree_dump.sql"

echo "=== 1/3 ローカル horse_pedigree を dump ==="
docker exec "$LOCAL_CT" pg_dump -U kbar -d kbar \
    --data-only --no-owner --table=public.horse_pedigree > "$DUMP_LOCAL"
echo "dump rows: $(grep -c '	' "$DUMP_LOCAL" || true) (概算)"

echo "=== 2/3 VPS へ転送 ==="
scp -i "$VPS_KEY" "$DUMP_LOCAL" "$VPS_HOST:$DUMP_REMOTE"

echo "=== 3/3 VPS で TRUNCATE → ロード ==="
ssh -i "$VPS_KEY" "$VPS_HOST" bash -s <<REMOTE
set -euo pipefail
set -a; . /opt/kbar/.env; set +a
echo "  TRUNCATE horse_pedigree ..."
docker exec kbar-postgres psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" -c "TRUNCATE horse_pedigree;"
echo "  COPY ロード ..."
docker exec -i kbar-postgres psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" < "$DUMP_REMOTE"
echo "  確認:"
docker exec kbar-postgres psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" -t -c "SELECT count(*) AS horse_pedigree_rows FROM horse_pedigree;"
REMOTE

echo "=== 完了 ==="
