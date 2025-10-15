#!/bin/bash
# Start catalog sync service for ComfyUI Bridge

set -e

echo "Starting catalog sync service..."

# Check if catalog sync is enabled
if [ "${CATALOG_AUTO_SYNC:-true}" != "true" ]; then
    echo "Catalog auto-sync is disabled"
    exit 0
fi

# Set default sync interval (1 hour)
SYNC_INTERVAL=${CATALOG_SYNC_INTERVAL:-3600}

# Start catalog sync in background
python3 /app/comfy-bridge/catalog_sync.py &
CATALOG_SYNC_PID=$!

echo "Catalog sync service started with PID: $CATALOG_SYNC_PID"

# Wait a moment to check if it started successfully
sleep 2

if ! ps -p $CATALOG_SYNC_PID > /dev/null 2>&1; then
    echo "Warning: Catalog sync service failed to start"
    exit 1
fi

echo "Catalog sync service is running"
