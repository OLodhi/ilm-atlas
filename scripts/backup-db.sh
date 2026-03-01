#!/bin/bash
# Daily PostgreSQL backup — run via cron
# Crontab: 0 3 * * * /opt/ilmatlas/scripts/backup-db.sh

BACKUP_DIR="/opt/ilmatlas/backups"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

docker compose -f /opt/ilmatlas/docker-compose.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-ilmatlas}" "${POSTGRES_DB:-ilmatlas}" \
    | gzip > "$BACKUP_DIR/ilmatlas_$TIMESTAMP.sql.gz"

# Prune old backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$KEEP_DAYS -delete

echo "Backup complete: ilmatlas_$TIMESTAMP.sql.gz"
