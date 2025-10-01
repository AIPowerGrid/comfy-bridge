#!/bin/bash
set -e

echo "================================================"
echo "  ComfyUI Bridge with Integrated ComfyUI"
echo "================================================"

# Function to check if ComfyUI is ready
wait_for_comfyui() {
    echo "Waiting for ComfyUI to be ready..."
    local max_attempts=60
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8188/system_stats > /dev/null 2>&1; then
            echo "✓ ComfyUI is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "  Waiting for ComfyUI... ($attempt/$max_attempts)"
        sleep 2
    done
    
    echo "✗ ComfyUI failed to start within expected time"
    return 1
}

# Start ComfyUI in the background
echo "Starting ComfyUI..."
cd /app/ComfyUI

# Start ComfyUI with proper settings
python3 main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    ${COMFYUI_EXTRA_ARGS} \
    > /tmp/comfyui.log 2>&1 &

COMFYUI_PID=$!
echo "ComfyUI started with PID: $COMFYUI_PID"

# Wait for ComfyUI to be ready
if ! wait_for_comfyui; then
    echo "Failed to start ComfyUI. Logs:"
    tail -n 50 /tmp/comfyui.log
    exit 1
fi

# Show ComfyUI startup logs
echo ""
echo "ComfyUI startup logs:"
echo "--------------------"
tail -n 20 /tmp/comfyui.log
echo "--------------------"
echo ""

# Start comfy-bridge
echo "Starting Comfy-Bridge..."
cd /app/comfy-bridge

# Check for required environment variables
if [ -z "$GRID_API_KEY" ]; then
    echo "WARNING: GRID_API_KEY not set. Bridge may not function properly."
fi

# Start the bridge
exec python3 -m comfy_bridge.cli

