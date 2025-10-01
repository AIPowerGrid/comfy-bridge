# 🚀 Quick Start Guide

Get ComfyUI Bridge running in under 5 minutes!

## Prerequisites

- Docker & Docker Compose installed
- NVIDIA GPU with drivers (for GPU acceleration)
- AI Power Grid API Key ([get one here](https://api.aipowergrid.io/register))

## Installation Steps

### 1. Get Your API Key

Sign up at https://api.aipowergrid.io/register and get your API key.

### 2. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/aipowergrid/comfy-bridge.git
cd comfy-bridge

# Copy environment template
cp env.example .env

# Edit .env and add your API key
nano .env  # or use your favorite editor
```

In the `.env` file, set:
```env
GRID_API_KEY=your_actual_api_key_here
GRID_WORKER_NAME=MyWorker.YourWallet
```

### 3. Start the Bridge

```bash
# Start everything (ComfyUI + Bridge)
docker-compose up -d

# View logs to confirm it's working
docker-compose logs -f
```

You should see:
1. ComfyUI starting up
2. Bridge connecting to AI Power Grid
3. "Advertising models" message

### 4. Verify It's Working

Open your browser:
- **ComfyUI Web UI**: http://localhost:8000
- **ComfyUI API**: http://localhost:8188

Check your worker on AI Power Grid dashboard to see it's online!

## Common Commands

```bash
# View logs
docker-compose logs -f

# Stop the bridge
docker-compose down

# Restart
docker-compose restart

# Check status
docker-compose ps

# Update and rebuild
git pull
docker-compose up -d --build
```

## Adding Models

### Option 1: Download into container

```bash
# Open shell in container
docker-compose exec comfy-bridge /bin/bash

# Navigate to models directory
cd /app/ComfyUI/models/checkpoints

# Download a model (example)
wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned.safetensors
```

### Option 2: Copy from local machine

```bash
# Copy model into container
docker cp your-model.safetensors comfy-bridge:/app/ComfyUI/models/checkpoints/
```

### Option 3: Mount local directory

Edit `docker-compose.yml` and add under `volumes`:
```yaml
- /path/to/your/models:/app/ComfyUI/models/checkpoints
```

## Troubleshooting

### "Container keeps restarting"

Check logs:
```bash
docker-compose logs comfy-bridge
```

Common causes:
- Invalid API key
- ComfyUI failed to start
- Out of memory

### "No GPU detected"

Verify NVIDIA Docker:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install nvidia-container-toolkit:
```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### "Bridge not receiving jobs"

1. Check API key is correct
2. Verify worker shows as "online" in dashboard
3. Check if you're advertising models:
   ```bash
   docker-compose logs | grep "Advertising models"
   ```
4. Make sure models are properly installed in ComfyUI

### "Out of memory errors"

Add to your `.env` file:
```env
COMFYUI_EXTRA_ARGS=--lowvram
```

Or for extreme cases:
```env
COMFYUI_EXTRA_ARGS=--novram --cpu
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

## Performance Tuning

### For High-End GPUs (24GB+ VRAM)

```env
COMFYUI_EXTRA_ARGS=--highvram
GRID_THREADS=4
```

### For Mid-Range GPUs (8-16GB VRAM)

```env
COMFYUI_EXTRA_ARGS=
GRID_THREADS=2
```

### For Low VRAM GPUs (4-8GB)

```env
COMFYUI_EXTRA_ARGS=--lowvram
GRID_THREADS=1
```

## Next Steps

- **Add more models**: Download models you want to support
- **Customize workflows**: Edit workflow files in `workflows/`
- **Monitor performance**: Check AI Power Grid dashboard
- **Earn rewards**: Process jobs and earn credits!

## Getting Help

- **Documentation**: See [DOCKER.md](DOCKER.md) for detailed Docker info
- **Issues**: Report bugs on GitHub
- **Community**: Join our Discord
- **Support**: Email support@aipowergrid.io

## Security Notes

⚠️ The ComfyUI web interface (port 8000) is exposed by default for convenience. 

For production:
1. Remove port 8000 from `docker-compose.yml` if you don't need the UI
2. Use a reverse proxy with authentication
3. Keep your `.env` file secure and never commit it to git

Happy bridging! 🚀

