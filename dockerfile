# Multi-stage build for ComfyUI Bridge with integrated ComfyUI
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Install ComfyUI
WORKDIR /app/ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git . && \
    pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install --no-cache-dir -r requirements.txt

# Create directories for ComfyUI models and outputs
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

# Install comfy-bridge
WORKDIR /app/comfy-bridge
COPY requirements.txt pyproject.toml ./
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir .

# Copy comfy-bridge code
COPY comfy_bridge ./comfy_bridge
COPY workflows ./workflows
COPY tests ./tests
COPY download_models_from_catalog.py model_manager.py model_configs.json get_gpu_info.py gpu_info_api.py catalog_sync.py start_catalog_sync.sh ./
RUN chmod +x get_gpu_info.py download_models_from_catalog.py gpu_info_api.py catalog_sync.py start_catalog_sync.sh

# Create startup script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

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
