#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "[UNIFORGE AI] Backing up PostgreSQL database..."
docker exec uniforge-postgres pg_dump -U uniforge -Fc uniforge_ai > "${BACKUP_DIR}/uniforge_${TIMESTAMP}.dump"
echo "[UNIFORGE AI] Backup written to ${BACKUP_DIR}/uniforge_${TIMESTAMP}.dump"
echo "To restore: docker exec -i uniforge-postgres pg_restore -U uniforge -d uniforge_ai --clean < ${BACKUP_DIR}/uniforge_${TIMESTAMP}.dump"
