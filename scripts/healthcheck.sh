#!/bin/bash
# Health check — run via cron every 5 minutes
# Crontab: */5 * * * * /opt/ilmatlas/scripts/healthcheck.sh

API_URL="http://localhost:8000/health"

status=$(curl -sf -o /dev/null -w "%{http_code}" "$API_URL" 2>/dev/null)

if [ "$status" != "200" ]; then
    echo "[$(date)] Health check FAILED (status: $status). Restarting..." >> /opt/ilmatlas/logs/healthcheck.log
    docker compose -f /opt/ilmatlas/docker-compose.yml restart backend
else
    echo "[$(date)] OK" >> /opt/ilmatlas/logs/healthcheck.log
fi
