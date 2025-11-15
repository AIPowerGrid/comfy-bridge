#!/bin/bash
set -e

echo "================================================"
echo "  ComfyUI Bridge with Integrated ComfyUI"
echo "================================================"

# Function to download required models
download_models() {
    echo "🔍 Checking configured models..."
    cd /app/comfy-bridge
    
    # Check if GRID_MODEL is set and not empty
    if [ -z "$GRID_MODEL" ] || [ "$GRID_MODEL" = "" ]; then
        echo "ℹ️  No models configured in GRID_MODEL"
        echo "   Please visit http://localhost:5000 to select models via the Management UI"
        return 0
    fi
    
    echo "📦 Downloading configured models..."
    # Run the model download script
    if python3 download_models_from_catalog.py --models $GRID_MODEL --config model_configs.json; then
        echo "✅ Model download completed successfully"
    else
        echo "⚠️  Model download had issues, but continuing..."
        echo "   You can manage models via the UI at http://localhost:5000"
        # Don't exit - allow container to continue
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
            echo "✅ ComfyUI is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "  Waiting for ComfyUI... ($attempt/$max_attempts)"
        sleep 2
    done
    
    echo "❌ ComfyUI failed to start within expected time"
    return 1
}

# Use preinstalled PyTorch; just print version for visibility
echo "🔧 Using preinstalled PyTorch (no runtime reinstall)"
python3 -c "import torch; print(f'✅ PyTorch {torch.__version__} with CUDA {torch.version.cuda} ready')" 2>/dev/null || true

# Create VAE symlink for ComfyUI compatibility (wan_2.1_vae.safetensors -> wan2.2_vae.safetensors)
if [ -f "/app/ComfyUI/models/vae/wan2.2_vae.safetensors" ] && [ ! -f "/app/ComfyUI/models/vae/wan_2.1_vae.safetensors" ]; then
    echo "🔗 Creating VAE symlink: wan_2.1_vae.safetensors -> wan2.2_vae.safetensors"
    ln -sf /app/ComfyUI/models/vae/wan2.2_vae.safetensors /app/ComfyUI/models/vae/wan_2.1_vae.safetensors
fi

# Download required models
download_models

# Start catalog sync service in background
echo "🔄 Starting catalog sync service..."
/app/comfy-bridge/start_catalog_sync.sh

# Ensure cache directory exists for downloads API locks
mkdir -p /app/comfy-bridge/.cache || true

# Start GPU info API in background
echo "🖥️ Starting GPU info API..."
python3 /app/comfy-bridge/gpu_info_api.py > /tmp/gpu_api.log 2>&1 &
GPU_API_PID=$!
echo "GPU info API started with PID: $GPU_API_PID"
sleep 2  # Give API time to start
if ! ps -p $GPU_API_PID > /dev/null 2>&1; then
    echo "⚠️  GPU API failed to start, check /tmp/gpu_api.log"
    cat /tmp/gpu_api.log
fi

# Start Downloads API in background
echo "📦 Starting Downloads API..."
python3 /app/comfy-bridge/downloads_api.py > /tmp/downloads_api.log 2>&1 &
DOWNLOADS_API_PID=$!
echo "Downloads API started with PID: $DOWNLOADS_API_PID"
sleep 1

# Function to detect GPU availability
detect_gpu() {
    echo "🔍 Detecting GPU availability..."
    if python3 -c "import torch; print('GPU available:', torch.cuda.is_available())" 2>/dev/null; then
        if python3 -c "import torch; torch.cuda.is_available()" 2>/dev/null; then
            echo "✅ GPU detected and available"
            return 0
        else
            echo "⚠️  GPU not available, falling back to CPU"
            return 1
        fi
    else
        echo "⚠️  GPU detection failed, falling back to CPU"
        return 1
    fi
}

# Start ComfyUI in the background
echo "Starting ComfyUI..."
cd /app/ComfyUI

# Detect GPU and set appropriate flags
if detect_gpu; then
    echo "🚀 Starting ComfyUI with GPU support..."
    COMFYUI_ARGS="--listen 0.0.0.0 --port 8188 ${COMFYUI_EXTRA_ARGS}"
else
    echo "🖥️ Starting ComfyUI with CPU fallback..."
    # Force CPU mode to avoid CUDA errors
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
exec python3 -m comfy_bridge.cli
