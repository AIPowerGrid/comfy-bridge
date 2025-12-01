#!/bin/bash
set -e

echo "================================================"
echo "  ComfyUI Bridge with Integrated ComfyUI"
echo "================================================"

# Function to download required models
download_models() {
    echo "🔍 Checking configured models..."
    cd /app/comfy-bridge

    # Remove legacy Wan 2.1 VAE symlink if it pointed at the 2.2 file so we re-download the real weights
    WAN21_PATH="/app/ComfyUI/models/vae/wan_2.1_vae.safetensors"
    if [ -L "$WAN21_PATH" ]; then
        echo "🧹 Removing legacy wan_2.1_vae.safetensors symlink so the correct 16-channel VAE can be downloaded"
        rm -f "$WAN21_PATH"
    fi
    
    if python3 <<'PY'
import os
from download_models_from_catalog import download_models, load_model_configs
from comfy_bridge.config import Settings
from comfy_bridge.model_mapper import ModelMapper

def parse_grid_model_env(raw: str) -> list[str]:
    if not raw:
        return []
    if "," in raw:
        tokens = raw.split(",")
    else:
        tokens = raw.split()
    return [token.strip() for token in tokens if token.strip()]

def build_alias_map():
    # Extra aliases for catalog IDs that differ from workflow filenames
    return {
        "chroma_final": "Chroma",
        "flux1.dev": "FLUX.1-dev",
        "flux1_dev": "FLUX.1-dev",
        "flux1_krea_dev": "flux.1-krea-dev",
        "flux1-krea-dev_fp8_scaled": "flux.1-krea-dev",
        "wan2_2_t2v_14b": "wan2.2-t2v-a14b",
        "wan2_2_t2v_14b_hq": "wan2.2-t2v-a14b-hq",
        "wan2_2_ti2v_5b": "wan2.2_ti2v_5B",
    }

grid_env_models = parse_grid_model_env(os.environ.get("GRID_MODEL", ""))
workflow_models = Settings.GRID_MODELS
requested_models = grid_env_models or workflow_models

if not requested_models:
    print("ℹ️  No models configured in GRID_MODEL or WORKFLOW_FILE")
    print("   Please visit http://localhost:5000 to select models via the Management UI")
    raise SystemExit(0)

config_path = os.environ.get("MODEL_CONFIG_PATH", "/app/comfy-bridge/model_configs.json")
catalog = load_model_configs(config_path)
catalog_keys = set(catalog.keys())
catalog_lower = {k.lower(): k for k in catalog_keys}
alias_map = build_alias_map()

def resolve_model_id(name: str) -> str:
    if name in catalog_keys:
        return name
    lower = catalog_lower.get(name.lower())
    if lower:
        return lower
    mapped = ModelMapper.DEFAULT_WORKFLOW_MAP.get(name)
    if mapped:
        if mapped in catalog_keys:
            return mapped
        lower = catalog_lower.get(mapped.lower())
        if lower:
            return lower
    special = alias_map.get(name) or alias_map.get(mapped or "")
    if special:
        if special in catalog_keys:
            return special
        lower = catalog_lower.get(special.lower())
        if lower:
            return lower
    return name

resolved = []
seen = set()
for model in requested_models:
    resolved_id = resolve_model_id(model)
    if resolved_id not in catalog_keys:
        print(f"[WARN] Model '{model}' not found in catalog; skipping.")
        continue
    if resolved_id in seen:
        continue
    seen.add(resolved_id)
    resolved.append(resolved_id)

if not resolved:
    print("ℹ️  No resolvable models found after mapping. Configure models via the Management UI.")
    raise SystemExit(0)

print(f"📦 Downloading configured models: {', '.join(resolved)}")
success = download_models(
    resolved,
    os.environ.get("MODELS_PATH", "/app/ComfyUI/models"),
    os.environ.get("STABLE_DIFFUSION_CATALOG", "/app/grid-image-model-reference/stable_diffusion.json"),
    config_path,
)

if success:
    print("✅ Model download completed successfully")
else:
    raise SystemExit(1)
PY
    then
        return 0
    else
        echo "⚠️  Model download had issues, but continuing..."
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
            echo "✅ ComfyUI is ready! (checked $attempt/$max_attempts)"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "  Waiting for ComfyUI... ($attempt/$max_attempts)" >&2
        sleep 2
    done
    
    echo "❌ ComfyUI failed to start within expected time" >&2
    return 1
}

# Use preinstalled PyTorch; just print version for visibility
echo "🔧 Using preinstalled PyTorch (no runtime reinstall)"
python3 -c "import torch; print(f'✅ PyTorch {torch.__version__} with CUDA {torch.version.cuda} ready')" 2>/dev/null || true

# Download required models
download_models
echo "🔗 Normalizing Wan asset locations..."
python3 - <<'PY' || echo "⚠️  Wan asset normalization reported an issue (continuing)"
from comfy_bridge.wan_assets import ensure_wan_symlinks
ensure_wan_symlinks()
PY

# Start catalog sync service in background
echo "🔄 Starting catalog sync service..."
/usr/bin/git config --global --add safe.directory /app/grid-image-model-reference >/dev/null 2>&1 || true
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
