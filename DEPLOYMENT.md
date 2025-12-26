# Deployment Guide

## Overview

This guide covers deploying the AI Power Grid ComfyUI worker with blockchain-based model registry.

## Prerequisites

- Docker and Docker Compose installed
- NVIDIA GPU with CUDA support (for GPU workers)
- Minimum 50GB free disk space
- Internet connection for blockchain RPC access
- API key from [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)

## Quick Deployment

### 1. Clone Repository

```bash
git clone https://github.com/AIPowerGrid/comfy-bridge.git
cd comfy-bridge
```

### 2. Configure Environment

```bash
cp env.example .env
nano .env  # or your preferred editor
```

**Required Configuration:**

```bash
# API Key (required)
GRID_API_KEY=your_api_key_here

# Worker Name (required - format: Name.WalletAddress)
GRID_WORKER_NAME=MyWorker.0xYourWalletAddress

# Blockchain Configuration (already set by default)
MODELVAULT_ENABLED=true
MODELVAULT_RPC_URL=https://mainnet.base.org
MODELVAULT_CONTRACT=0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
```

### 3. Build and Start

```bash
# Build the Docker images
docker-compose build

# Start the services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access Management UI

Open http://localhost:5000 in your browser to:
- Select models to host
- Monitor job processing
- View earnings and statistics

## Blockchain Configuration

### ModelVault Contract

The worker connects to the ModelVault smart contract on Base Mainnet to discover and validate models.

**Network Details:**
- **Chain**: Base Mainnet
- **Chain ID**: 8453
- **RPC URL**: https://mainnet.base.org
- **Contract**: `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609`

### Alternative RPC Endpoints

If the default RPC is slow or unavailable, you can use alternative Base Mainnet endpoints:

```bash
# Alchemy (requires API key)
MODELVAULT_RPC_URL=https://base-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Infura (requires API key)
MODELVAULT_RPC_URL=https://base-mainnet.infura.io/v3/YOUR_API_KEY

# Public endpoints
MODELVAULT_RPC_URL=https://mainnet.base.org
MODELVAULT_RPC_URL=https://base.publicnode.com
```

### Disabling Blockchain (Not Recommended)

If you need to disable blockchain validation (not recommended for production):

```bash
MODELVAULT_ENABLED=false
```

**Warning**: Disabling blockchain validation means:
- No model verification
- No access to blockchain-registered models
- Worker may not receive jobs from the Grid

## Docker Compose Services

### comfy-bridge

Main worker service that:
- Connects to AI Power Grid API
- Processes generation jobs
- Manages ComfyUI backend
- Validates models via blockchain

**Ports:**
- `5000`: Management UI
- `8188`: ComfyUI API (internal)

**Volumes:**
- `comfyui_models`: Persistent model storage
- `comfyui_output`: Generated outputs

### Management UI

Web interface for:
- Model selection and download
- Job monitoring
- Worker statistics
- Blockchain model browsing

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GRID_API_KEY` | Your API key from dashboard | `aipg_abc123...` |
| `GRID_WORKER_NAME` | Worker identifier | `MyWorker.0x123...` |

### Blockchain (Pre-configured)

| Variable | Description | Default |
|----------|-------------|---------|
| `MODELVAULT_ENABLED` | Enable blockchain registry | `true` |
| `MODELVAULT_RPC_URL` | Base Mainnet RPC endpoint | `https://mainnet.base.org` |
| `MODELVAULT_CONTRACT` | ModelVault contract address | `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `GRID_NSFW` | Allow NSFW content | `false` |
| `GRID_THREADS` | Concurrent job processing | `2` |
| `GRID_MAX_PIXELS` | Maximum output resolution | `1048576` |
| `DEBUG` | Enable debug logging | `false` |
| `HUGGING_FACE_API_KEY` | HF API token (for downloads) | - |
| `CIVITAI_API_KEY` | Civitai API token (for downloads) | - |

## Production Deployment

### System Requirements

**Minimum:**
- 8GB RAM
- 50GB disk space
- 4 CPU cores
- NVIDIA GPU with 8GB VRAM

**Recommended:**
- 16GB+ RAM
- 200GB+ SSD storage
- 8+ CPU cores
- NVIDIA GPU with 24GB+ VRAM

### Security Considerations

1. **API Keys**: Store securely, never commit to version control
2. **Firewall**: Only expose port 5000 if remote access needed
3. **Updates**: Regularly pull latest images for security patches
4. **Monitoring**: Set up log aggregation and alerting

### High Availability

For production deployments:

1. **Multiple Workers**: Run multiple worker instances
2. **Load Balancing**: Use reverse proxy (nginx/traefik)
3. **Monitoring**: Prometheus + Grafana for metrics
4. **Backup**: Regular backups of model cache

### Resource Limits

Configure Docker resource limits in `docker-compose.yml`:

```yaml
services:
  comfy-bridge:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## Troubleshooting

### Blockchain Connection Issues

**Symptom**: "Error fetching total models: execution reverted"

**Solutions**:
1. Check RPC URL is correct
2. Try alternative RPC endpoint
3. Verify internet connectivity
4. Check firewall allows HTTPS (443) outbound

### No Models Available

**Symptom**: "No models resolved from WORKFLOW_FILE"

**Solutions**:
1. Verify blockchain connection is working
2. Check models are registered on-chain
3. Restart worker to refresh model cache
4. Check logs for specific errors

### Docker Build Failures

**Symptom**: Build fails during model download

**Solutions**:
1. Check disk space (need 50GB+)
2. Verify API keys are correct
3. Check internet connection
4. Try building without cache: `docker-compose build --no-cache`

### GPU Not Detected

**Symptom**: "GPU not available, falling back to CPU"

**Solutions**:
1. Install NVIDIA Container Toolkit
2. Verify GPU works: `nvidia-smi`
3. Restart Docker daemon
4. Check docker-compose.yml has GPU configuration

## Monitoring

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f comfy-bridge

# View last 100 lines
docker-compose logs --tail=100 comfy-bridge
```

### Health Checks

```bash
# Check service status
docker-compose ps

# Check ComfyUI health
curl http://localhost:8188/system_stats

# Check Management UI
curl http://localhost:5000/api/health
```

### Metrics

Monitor these key metrics:
- Jobs processed per hour
- Average job completion time
- GPU utilization
- VRAM usage
- Disk space remaining

## Updating

### Update Worker

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose build

# Restart services
docker-compose down
docker-compose up -d
```

### Update Models

Models are automatically updated from the blockchain registry. To force refresh:

```bash
# Restart worker
docker-compose restart comfy-bridge
```

## Backup and Recovery

### Backup Models

```bash
# Backup model cache
docker run --rm -v comfyui_models:/data -v $(pwd):/backup ubuntu tar czf /backup/models-backup.tar.gz /data
```

### Restore Models

```bash
# Restore from backup
docker run --rm -v comfyui_models:/data -v $(pwd):/backup ubuntu tar xzf /backup/models-backup.tar.gz -C /
```

### Backup Configuration

```bash
# Backup .env file
cp .env .env.backup

# Backup docker-compose overrides
cp docker-compose.override.yml docker-compose.override.yml.backup
```

## Advanced Configuration

### Custom ComfyUI Arguments

```bash
# Add to .env
COMFYUI_EXTRA_ARGS=--lowvram --preview-method auto
```

### Custom Model Path

```bash
# Add to .env
MODELS_PATH=/custom/path/to/models
```

Then mount in docker-compose.yml:

```yaml
volumes:
  - /custom/path/to/models:/app/ComfyUI/models
```

### Multiple GPU Support

Edit docker-compose.yml:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all  # Use all GPUs
          capabilities: [gpu]
```

## Support

- **Documentation**: https://github.com/AIPowerGrid/comfy-bridge
- **Dashboard**: https://dashboard.aipowergrid.io
- **Issues**: https://github.com/AIPowerGrid/comfy-bridge/issues
- **Blockchain Explorer**: https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609

## Migration from JSON Catalog

If upgrading from a version that used `stable_diffusion.json`:

1. **Remove Old Config**: Delete `GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH` from `.env`
2. **Update RPC**: Ensure `MODELVAULT_RPC_URL` is set
3. **Rebuild**: Run `docker-compose build --no-cache`
4. **Verify**: Check logs show "Loaded X models from blockchain"

The blockchain registry is now the only source of model information. No JSON files are used.
