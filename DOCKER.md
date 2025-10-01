# Docker Deployment Guide

Complete guide for deploying ComfyUI Bridge with integrated ComfyUI using Docker.

## Quick Start

```bash
# 1. Configure
cp env.example .env
# Edit .env and add your GRID_API_KEY

# 2. Start
docker-compose up -d

# 3. Monitor
docker-compose logs -f
```

**Prerequisites:** Docker, Docker Compose, NVIDIA Docker (for GPU), API key from https://api.aipowergrid.io/register

## 📦 What's Included

The Docker container includes:
- **ComfyUI** - Automatically cloned and configured
- **Comfy-Bridge** - Connected to AI Power Grid
- **All dependencies** - PyTorch with CUDA 12.1 support
- **Model directories** - Persistent storage for models
- **Auto-startup** - ComfyUI starts first, then bridge connects

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRID_API_KEY` | *required* | Your AI Power Grid API key |
| `GRID_WORKER_NAME` | `ComfyBridge-Worker` | Worker name for the grid |
| `COMFYUI_URL` | `http://localhost:8188` | Internal ComfyUI URL |
| `GRID_API_URL` | `https://api.aipowergrid.io/api` | Grid API endpoint |
| `GRID_NSFW` | `false` | Allow NSFW content generation |
| `GRID_THREADS` | `2` | Concurrent job processing threads |
| `GRID_MAX_PIXELS` | `1048576` | Max output resolution |
| `WORKFLOW_FILE` | *(empty)* | Specific workflows to use |
| `GRID_MODEL` | *(empty)* | Models to advertise (auto-detect if empty) |
| `COMFYUI_EXTRA_ARGS` | *(empty)* | Extra args for ComfyUI (e.g., `--highvram`) |

### Volume Mounts

The docker-compose file creates persistent volumes for:

- **Models**: `/app/ComfyUI/models` - Store your AI models here
- **Output**: `/app/ComfyUI/output` - Generated images/videos
- **Input**: `/app/ComfyUI/input` - Input images for processing
- **Workflows**: `./workflows` - Custom workflow files (read-only)

### Adding Models

To use your own models, you can:

**Option 1: Use Docker volumes** (recommended)
```bash
# Copy models into the volume
docker cp your_model.safetensors comfy-bridge:/app/ComfyUI/models/checkpoints/
```

**Option 2: Mount local directory**
Add to docker-compose.yml under `volumes`:
```yaml
- /path/to/your/models:/app/ComfyUI/models:ro
```

## 🖥️ Accessing ComfyUI

While the bridge runs headless, ComfyUI's web interface is accessible:

- **Web UI**: http://localhost:8000
- **API**: http://localhost:8188

## 🏗️ Building the Image

### Standard Build

```bash
docker build -t comfy-bridge:latest .
```

### Build with specific ComfyUI version

Edit `Dockerfile` and change the ComfyUI clone command:

```dockerfile
RUN git clone --branch v1.0.0 https://github.com/comfyanonymous/ComfyUI.git .
```

### Multi-platform Build

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t comfy-bridge:latest .
```

## 🔍 Troubleshooting

### Check Container Logs

```bash
# All logs
docker-compose logs

# Just ComfyUI startup
docker exec comfy-bridge tail -f /tmp/comfyui.log

# Just bridge logs
docker-compose logs comfy-bridge
```

### Verify GPU Access

```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Check in your container
docker exec comfy-bridge nvidia-smi
```

### ComfyUI Not Starting

Check ComfyUI logs:
```bash
docker exec comfy-bridge cat /tmp/comfyui.log
```

Common issues:
- **Out of memory**: Add `--lowvram` or `--novram` to `COMFYUI_EXTRA_ARGS`
- **CUDA errors**: Ensure nvidia-docker is properly installed
- **Port conflicts**: Change ports in docker-compose.yml

### Bridge Not Connecting

1. **Check API key**: Ensure `GRID_API_KEY` is set correctly
2. **Check ComfyUI**: Verify it's running with `curl http://localhost:8188/system_stats`
3. **Check logs**: Look for connection errors in bridge logs

## 🔄 Updates

### Update ComfyUI

```bash
docker-compose exec comfy-bridge sh -c "cd /app/ComfyUI && git pull"
docker-compose restart
```

### Update Comfy-Bridge

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

## 💾 Backup

### Backup Models

```bash
docker run --rm -v comfy-bridge_comfyui-models:/models -v $(pwd):/backup ubuntu tar czf /backup/models-backup.tar.gz -C /models .
```

### Restore Models

```bash
docker run --rm -v comfy-bridge_comfyui-models:/models -v $(pwd):/backup ubuntu tar xzf /backup/models-backup.tar.gz -C /models
```

## 🚢 Production Deployment

### Using Docker Swarm

```bash
docker stack deploy -c docker-compose.yml comfy-bridge
```

### Using Kubernetes

See `k8s/` directory for Kubernetes manifests (coming soon).

### Resource Limits

Add to docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 16G
    reservations:
      cpus: '4'
      memory: 8G
```

## 📊 Monitoring

### Health Checks

The container includes a health check that pings ComfyUI every 30 seconds.

Check health:
```bash
docker inspect --format='{{.State.Health.Status}}' comfy-bridge
```

### Metrics

Monitor GPU usage:
```bash
watch -n 1 docker exec comfy-bridge nvidia-smi
```

## 🛡️ Security

### Running as Non-Root

The container runs as user `aiworker` (UID 1000) for security.

### Network Isolation

For production, consider using Docker networks:
```yaml
networks:
  internal:
    internal: true
  external:
```

### Secrets Management

Use Docker secrets instead of environment variables:
```bash
echo "your_api_key" | docker secret create grid_api_key -
```

## 📝 License

See main repository LICENSE file.

