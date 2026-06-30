#!/usr/bin/env bash
# sync_jravan_derived_to_vps.sh
# 自宅PC専用: JV-Data由来の「自己完結テーブル」をまとめて本番VPSへデータ同期する。
# スキーマは alembic マイグレーションでVPS側に作成済みである前提（master push → デプロイ時に自動適用）。
#
# 対象テーブル（race_id / netkeiba_id キーでアプリ races と結合・FDW非依存）:
#   - horse_pedigree      血統（父/母/父父/母父）
#   - confirmed_win_odds  確定単勝オッズ
#   - confirmed_payouts   確定払戻
#
# 流れ（テーブルごと）:
#   1. ローカル kbar-postgres から data-only で pg_dump
#   2. scp でVPSへ転送
#   3. VPS側で TRUNCATE → ロード（VPSの /opt/kbar/.env から DB認証を読む）
#
# 使い方:  bash backend/jravan/sync_jravan_derived_to_vps.sh
# 前提:    ローカルで各テーブルが populate 済み（populate_*.sql 実行後）
set -euo pipefail

# Configure via env: VPS_HOST (user@host) and VPS_KEY (path to SSH private key)
VPS_HOST="${VPS_HOST:?set VPS_HOST=user@host}"
VPS_KEY="${VPS_KEY:?set VPS_KEY=/path/to/ssh_key}"
LOCAL_CT="kbar-postgres"
TABLES=(horse_pedigree confirmed_win_odds confirmed_payouts)

for t in "${TABLES[@]}"; do
  echo "================= $t ================="
  DUMP="/tmp/${t}_dump.sql"
  echo "  1/3 dump (local)"
  docker exec "$LOCAL_CT" pg_dump -U kbar -d kbar \
      --data-only --no-owner --table="public.${t}" > "$DUMP"
  echo "  2/3 scp -> VPS"
  scp -i "$VPS_KEY" -o ConnectTimeout=15 "$DUMP" "$VPS_HOST:$DUMP" >/dev/null
  echo "  3/3 truncate + load (VPS)"
  ssh -i "$VPS_KEY" -o ConnectTimeout=15 "$VPS_HOST" \
    "set -a; . /opt/kbar/.env; set +a; \
     docker exec kbar-postgres psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c 'TRUNCATE ${t};' >/dev/null; \
     docker exec -i kbar-postgres psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" < $DUMP | tail -1; \
     docker exec kbar-postgres psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -t -c 'SELECT count(*) FROM ${t};'"
done

echo "=== 完了: 全テーブル同期済み ==="
