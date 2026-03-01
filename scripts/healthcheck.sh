#!/bin/bash
# Health check — run via cron every 5 minutes
# Crontab: */5 * * * * /opt/ilmatlas/scripts/healthcheck.sh

LOG_DIR="/opt/ilmatlas/logs"
API_URL="http://localhost:8000/health"

mkdir -p "$LOG_DIR"

status=$(curl -sf -o /dev/null -w "%{http_code}" "$API_URL" 2>/dev/null)

if [ "$status" != "200" ]; then
    echo "[$(date)] Health check FAILED (status: $status). Restarting..." >> "$LOG_DIR/healthcheck.log"
    docker compose -f /opt/ilmatlas/docker-compose.yml restart backend
else
    echo "[$(date)] OK" >> "$LOG_DIR/healthcheck.log"
fi
