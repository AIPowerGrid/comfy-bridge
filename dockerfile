# Multi-stage build for ComfyUI Bridge with integrated ComfyUI
# Using CUDA 12.8 for Blackwell GPU support (RTX PRO 6000)
# PyTorch 2.7.0+ with CUDA 12.8 includes Blackwell (sm_120) support
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04 AS base

# Set environment variables
# Note: PIP_NO_CACHE_DIR removed to allow cache mounts for faster rebuilds
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies with apt cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create working directories
WORKDIR /app
RUN mkdir -p /app/ComfyUI /app/comfy-bridge

# Install ComfyUI with git cache mount
WORKDIR /app
ARG COMFYUI_VERSION=main
RUN --mount=type=cache,target=/root/.cache/git \
    rm -rf ComfyUI && \
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI && \
    (cd ComfyUI && git checkout ${COMFYUI_VERSION} 2>/dev/null || true) && \
    cd ComfyUI && \
    grep -v -E "^(torch|torchvision|torchaudio)([=<>].*)?$" requirements.txt > /tmp/requirements_no_torch.txt

# Install ComfyUI dependencies with pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --timeout 120 -r /tmp/requirements_no_torch.txt

# Install ComfyUI-WanVideoWrapper custom node extension with git and pip cache mounts
WORKDIR /app/ComfyUI/custom_nodes
RUN --mount=type=cache,target=/root/.cache/git \
    --mount=type=cache,target=/root/.cache/pip \
    git clone --depth 1 https://github.com/Kijai/ComfyUI-WanVideoWrapper.git ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    if [ -f requirements.txt ]; then \
        pip3 install --timeout 120 -r requirements.txt; \
    fi && \
    # Try to install optional dependencies for WanVideoWrapper
    pip3 install --timeout 120 onnxruntime || echo "Optional: onnxruntime not available"

# Install ComfyUI-WanMoeKSampler custom node extension (provides SplitSigmasAtT)
RUN --mount=type=cache,target=/root/.cache/git \
    --mount=type=cache,target=/root/.cache/pip \
    git clone --depth 1 https://github.com/stduhpf/ComfyUI-WanMoeKSampler.git ComfyUI-WanMoeKSampler && \
    cd ComfyUI-WanMoeKSampler && \
    if [ -f requirements.txt ]; then \
        pip3 install --timeout 120 -r requirements.txt; \
    fi

# Create directories for ComfyUI models and outputs
WORKDIR /app
RUN mkdir -p \
    /app/ComfyUI/models/checkpoints \
    /app/ComfyUI/models/diffusion_models \
    /app/ComfyUI/models/unet \
    /app/ComfyUI/models/vae \
    /app/ComfyUI/models/clip \
    /app/ComfyUI/models/text_encoders \
    /app/ComfyUI/models/loras \
    /app/ComfyUI/input \
    /app/ComfyUI/output \
    /app/ComfyUI/temp

# Install comfy-bridge with pip cache mount
WORKDIR /app/comfy-bridge
COPY requirements.txt pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt && \
    pip3 install .

# Copy comfy-bridge code
COPY comfy_bridge ./comfy_bridge
COPY workflows ./workflows
COPY tests ./tests
# Copy utility scripts (blockchain-based model download with fallback catalog)
COPY download_models_from_chain.py model_manager.py get_gpu_info.py gpu_info_api.py downloads_api.py model_catalog.py ./
RUN chmod +x get_gpu_info.py download_models_from_chain.py gpu_info_api.py downloads_api.py

# Install optional performance dependencies (inlined to avoid Windows CRLF issues)
RUN --mount=type=cache,target=/root/.cache/pip \
    echo "Installing optional performance dependencies..." && \
    pip3 install --timeout 60 onnxruntime>=1.15.0 || echo "onnxruntime not available" && \
    pip3 install --timeout 60 flash-attn>=2.0.0 || echo "flash-attn not available" && \
    pip3 install --timeout 60 sageattention>=1.0.0 || echo "sageattention not available" && \
    echo "Optional dependencies installation complete"

# Create startup script (strip CRLF for Windows compatibility)
COPY docker-entrypoint.sh /app/
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

# Build arguments for model configuration (must be declared before use)
ARG GRID_MODEL=""
ARG WORKFLOW_FILE=""
ARG MODELVAULT_CONTRACT=""
ARG MODELVAULT_RPC=""
ARG HUGGING_FACE_API_KEY=""
ARG CIVITAI_API_KEY=""

# Install PyTorch 2.9.1 with CUDA 12.8 for Blackwell GPU support (sm_120)
# Use cache mount for pip to persist PyTorch wheels (900MB+ download)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 uninstall -y torch torchvision torchaudio 2>/dev/null || true && \
    pip3 install --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/cu128 torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 && \
    python3 -c "import torch, torchvision, torchaudio; print(f'PyTorch {torch.__version__} installed for CUDA {torch.version.cuda}'); print(f'torchvision {torchvision.__version__}'); print(f'torchaudio {torchaudio.__version__}')"

# Model downloads during build are disabled to speed up build process
# Models should be downloaded via the Management UI (http://localhost:5000) at runtime
# Users can select and download models through the aipg-art-gallery interface
RUN echo "Model downloads during build are disabled" && \
    echo "Please use the Management UI at http://localhost:5000 to download models" && \
    echo "Models will be downloaded at runtime via the UI"

# Create non-root user
RUN groupadd --gid 1000 aiworker && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home aiworker && \
    chown -R aiworker:aiworker /app

USER aiworker

# Expose ports
# 8000 = ComfyUI web interface
# 8188 = ComfyUI API (default)
EXPOSE 8000 8188

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

# Set working directory back to app root
WORKDIR /app

# Use the entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
