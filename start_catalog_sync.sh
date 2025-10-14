#!/bin/bash
# Start catalog sync service

echo "🔄 Starting catalog sync service..."
python3 /app/comfy-bridge/catalog_sync.py --continuous > /tmp/catalog_sync.log 2>&1 &
CATALOG_SYNC_PID=$!
echo "Catalog sync service started with PID: $CATALOG_SYNC_PID"
sleep 2  # Give service time to start
if ! ps -p $CATALOG_SYNC_PID > /dev/null 2>&1; then
    echo "⚠️  Catalog sync service failed to start, check /tmp/catalog_sync.log"
    cat /tmp/catalog_sync.log
fi
