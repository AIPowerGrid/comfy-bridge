#!/bin/bash
set -e

echo "================================================"
echo "  ComfyUI Bridge - Blockchain Model Registry"
echo "================================================"

# Function to download required models FROM BLOCKCHAIN
download_models() {
    echo "Downloading models from blockchain registry..."
    cd /app/comfy-bridge

    # Remove legacy Wan 2.1 VAE symlink if it pointed at the 2.2 file
    WAN21_PATH="/app/ComfyUI/models/vae/wan_2.1_vae.safetensors"
    if [ -L "$WAN21_PATH" ]; then
        echo "Removing legacy wan_2.1_vae.safetensors symlink"
        rm -f "$WAN21_PATH"
    fi
    
    if python3 <<'PY'
import os
import sys

# Import blockchain-based download
from download_models_from_chain import download_models_from_chain

# Parse model list from environment
def parse_model_env(raw: str) -> list[str]:
    if not raw:
        return []
    if "," in raw:
        tokens = raw.split(",")
    else:
        tokens = raw.split()
    return [token.strip() for token in tokens if token.strip()]

# Get models from environment
grid_env = os.environ.get("GRID_MODEL", "")
workflow_env = os.environ.get("WORKFLOW_FILE", "")

requested_models = parse_model_env(grid_env) or parse_model_env(workflow_env)

if not requested_models:
    print("No models configured in GRID_MODEL or WORKFLOW_FILE")
    print("   Please visit http://localhost:5000 to select models via the Management UI")
    sys.exit(0)

print(f"Downloading configured models: {', '.join(requested_models)}")

models_path = os.environ.get("MODELS_PATH", "/app/ComfyUI/models")
success = download_models_from_chain(requested_models, models_path)

if success:
    print("Model download completed successfully")
    sys.exit(0)
else:
    print("Some models may not have download URLs registered")
    print("   Models without blockchain download info need to be registered with the V2 contract")
    sys.exit(0)  # Don't fail - allow worker to start
PY
    then
        return 0
    else
        echo "Model download had issues, but continuing..."
        echo "   You can manage models via the UI at http://localhost:5000"
        return 0
    fi
}

# Function to check if ComfyUI is ready
wait_for_comfyui() {
    echo "Waiting for ComfyUI to be ready..."
    local max_attempts=60
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8188/system_stats > /dev/null 2>&1; then
            attempt=$((attempt + 1))
            echo "ComfyUI is ready! (checked $attempt/$max_attempts)"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "  Waiting for ComfyUI... ($attempt/$max_attempts)" >&2
        sleep 2
    done
    
    echo "ComfyUI failed to start within expected time" >&2
    return 1
}

# Use preinstalled PyTorch
echo "Using preinstalled PyTorch (no runtime reinstall)"
python3 -c "import torch; print(f'PyTorch {torch.__version__} with CUDA {torch.version.cuda} ready')" 2>/dev/null || true

# Ensure cache directory exists for downloads API locks
mkdir -p /app/comfy-bridge/.cache || true

# Start GPU info API EARLY so UI can show GPU info during downloads
echo "Starting GPU info API (early start)..."
python3 /app/comfy-bridge/gpu_info_api.py > /tmp/gpu_api.log 2>&1 &
GPU_API_PID=$!
echo "GPU info API started with PID: $GPU_API_PID"
sleep 2
if ! ps -p $GPU_API_PID > /dev/null 2>&1; then
    echo "GPU API failed to start, check /tmp/gpu_api.log"
    cat /tmp/gpu_api.log
else
    echo "GPU API running on port 8001"
fi

# Download required models FROM BLOCKCHAIN
download_models

# Normalize Wan asset locations
echo "Normalizing Wan asset locations..."
python3 - <<'PY' || echo "Wan asset normalization reported an issue (continuing)"
from comfy_bridge.wan_assets import ensure_wan_symlinks
ensure_wan_symlinks()
PY

# Start Downloads API in background (GPU API already started above)
echo "Starting Downloads API..."
python3 /app/comfy-bridge/downloads_api.py > /tmp/downloads_api.log 2>&1 &
DOWNLOADS_API_PID=$!
echo "Downloads API started with PID: $DOWNLOADS_API_PID"
sleep 1

# Function to detect GPU availability
detect_gpu() {
    echo "Detecting GPU availability..."
    if python3 -c "import torch; print('GPU available:', torch.cuda.is_available())" 2>/dev/null; then
        if python3 -c "import torch; torch.cuda.is_available()" 2>/dev/null; then
            echo "GPU detected and available"
            return 0
        else
            echo "GPU not available, falling back to CPU"
            return 1
        fi
    else
        echo "GPU detection failed, falling back to CPU"
        return 1
    fi
}

# Start ComfyUI in the background
echo "Starting ComfyUI..."
cd /app/ComfyUI

# Detect GPU and set appropriate flags
if detect_gpu; then
    echo "Starting ComfyUI with GPU support..."
    COMFYUI_ARGS="--listen 0.0.0.0 --port 8188 ${COMFYUI_EXTRA_ARGS}"
else
    echo "Starting ComfyUI with CPU fallback..."
    COMFYUI_ARGS="--listen 0.0.0.0 --port 8188 --cpu ${COMFYUI_EXTRA_ARGS}"
fi

# Start ComfyUI with proper settings
python3 main.py ${COMFYUI_ARGS} > /tmp/comfyui.log 2>&1 &

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
exec python3 -m comfy_bridge
