<div align="center">

![AI Power Grid Logo](management-ui-nextjs/public/AIPGsimplelogo.png)

# 🚀 AI Power Grid - ComfyUI Bridge Worker

**Turn your GPU into an AI processing powerhouse and earn AIPG tokens!**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-GPU-green?logo=nvidia)](https://www.nvidia.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

**🎨 Generate stunning AI art, videos, and images while earning rewards**

</div>

## 🎯 Quick Start Guide

### Step 1: Get Your API Key 🔑
1. Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Create a free account and verify your email
3. Go to "API Keys" section and generate a new key
4. Copy the key (starts with `aipg_`)

> **📋 Detailed Setup**: See [API Key Configuration](#-api-key-configuration) section at the bottom for complete instructions.

### Step 2: System Requirements 💻
- **[Docker](https://www.docker.com/get-started)** with **[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)** installed
- **NVIDIA GPU** with at least 6GB VRAM
- **8GB+ RAM** recommended
- **50GB+ free disk space** for models

> **🚀 Coming Soon**: AMD ROCm support for RX 7000 series and newer GPUs

### Step 3: Clone & Configure 📥
```bash
git clone https://github.com/aipowergrid/comfy-bridge.git
cd comfy-bridge
cp env.example .env
```

Edit `.env` and add your information:
```bash
# Required: Your API key from dashboard.aipowergrid.io
GRID_API_KEY=your_api_key_here

# Required: Worker name format: Name.WalletAddress
GRID_WORKER_NAME=MyWorker.YourWalletAddress

# Optional: For faster downloads
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

### Step 4: Launch the Worker 🚀
```bash
docker-compose up -d
```

### Step 5: Configure Models 🎨
Open [http://localhost:5000](http://localhost:5000) in your browser:

1. **Browse Models**: Select models that fit your GPU VRAM
2. **Download**: Click download for chosen models
3. **Start Hosting**: Click "Start Hosting" to begin earning

**🎉 You're now earning AIPG tokens!**

---

## 🔄 Managing Updates & Maintenance

### Pulling Latest Updates 📥
To get the latest features and fixes:

```bash
# Navigate to your comfy-bridge directory
cd comfy-bridge

# Pull the latest changes from GitHub
git pull origin main

# Rebuild containers to apply updates
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Applying Updates Without Data Loss 💾
Your models and configuration are stored in persistent volumes, so updates won't affect your data:

```bash
# Stop containers gracefully
docker-compose down

# Pull latest code
git pull origin main

# Rebuild with latest changes
docker-compose build --no-cache

# Start with existing data intact
docker-compose up -d
```

### Checking Update Status 📊
```bash
# View running containers
docker-compose ps

# Check logs for any issues
docker-compose logs -f

# Verify API is responding
curl http://localhost:5000/api/models | head -c 100
```

### Complete Reset (Fresh Start) 🔄
If you need to start completely fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Remove all images (optional)
docker system prune -a

# Pull latest code
git pull origin main

# Fresh build and start
docker-compose build --no-cache
docker-compose up -d
```

> **⚠️ Warning**: `docker-compose down -v` will delete all downloaded models and configuration. Only use this if you want a completely fresh start.

---

## 🛠️ Advanced Configuration

### Environment Variables 🔧
Complete list of available environment variables:

```bash
# Required
GRID_API_KEY=your_api_key_here
GRID_WORKER_NAME=MyWorker.YourWalletAddress

# Optional - Performance
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token

# Optional - Advanced
GRID_API_URL=https://api.aipowergrid.io
COMFYUI_HOST=localhost
COMFYUI_PORT=8188
MANAGEMENT_UI_PORT=5000
```

### GPU Selection 🎮
To use a specific GPU:

```bash
# Use GPU 0 (default)
docker-compose up -d

# Use specific GPU
docker run --gpus '"device=1"' comfy-bridge-comfy-bridge

# Use multiple GPUs
docker run --gpus '"device=0,1"' comfy-bridge-comfy-bridge
```

### Resource Limits 📈
Adjust resource usage in `docker-compose.yml`:

```yaml
services:
  comfy-bridge:
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          memory: 8G
```

## 💻 GPU Requirements & Model Support

| Model Type | VRAM Needed | Examples | Use Cases |
|------------|-------------|----------|-----------|
| **SD 1.5** | 6GB | Realistic Vision, Deliberate | General image generation |
| **SDXL** | 8GB | SDXL 1.0, Juggernaut XL | High-resolution images |
| **Flux** | 12GB | Flux.1-Schnell, Flux.1-Krea | Advanced image generation |
| **Video (5B)** | 12GB | wan2.2_ti2v_5B | Text-to-video, Image-to-video |
| **Video (14B)** | 16GB | wan2.2-t2v-a14b | High-quality video generation |

> **💡 Pro Tip**: Start with SD 1.5 models if you have limited VRAM, then upgrade to SDXL or Flux as you expand your setup!

## 🔧 Troubleshooting & Support

### Common Issues & Solutions

**🔍 Can't see my GPU?**
- Run `nvidia-smi` in your terminal to verify your GPU is detected
- Make sure NVIDIA Container Toolkit is installed
- Check Docker has GPU access: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

**📥 Models won't download?**
- Check your internet connection
- Verify your API key in the `.env` file
- Ensure you have enough disk space (50GB+ recommended)

**💰 Not receiving jobs?**
- Confirm models show "Hosting" status (green) in the UI
- Check your worker name format: `Name.WalletAddress`
- Verify your API key is valid at [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)

**🔄 Containers won't start after update?**
- Check for port conflicts: `netstat -tulpn | grep :5000`
- Verify Docker is running: `docker --version`
- Check system resources: `docker system df`

**📊 View logs:**
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f comfy-bridge
docker-compose logs -f management-ui

# View last 50 lines
docker-compose logs --tail=50
```

### 🚀 Performance Optimization

**Faster Downloads:**
Add these to your `.env` file for faster model downloads:
```bash
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

**GPU Memory Optimization:**
- Close other GPU-intensive applications
- Use `--gpus '"device=0"'` to specify which GPU to use
- Monitor VRAM usage with `nvidia-smi`

**System Resource Monitoring:**
```bash
# Check container resource usage
docker stats

# Monitor disk space
df -h

# Check GPU utilization
nvidia-smi -l 1
```

### 🔧 Maintenance Commands

**Daily Health Check:**
```bash
# Quick status check
docker-compose ps
curl -s http://localhost:5000/api/models | jq 'keys | length'

# Check for updates
git fetch origin
git log HEAD..origin/main --oneline
```

**Weekly Maintenance:**
```bash
# Clean up unused Docker resources
docker system prune -f

# Check disk usage
du -sh persistent_volumes/

# Backup configuration
cp .env .env.backup
```

**Monthly Deep Clean:**
```bash
# Remove unused images and containers
docker system prune -a -f

# Update to latest version
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 Additional Resources

- **📖 Documentation**: [aipowergrid.io](https://aipowergrid.io)
- **💬 Community**: Join our Discord for support and discussions
- **🐛 Issues**: Report bugs and feature requests on GitHub
- **📊 Dashboard**: Monitor your earnings at [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)

---

## 🔑 API Key Configuration

### Getting Your AI Power Grid API Key

**Step 1: Create Account**
1. Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Click "Sign Up" and create your free account
3. Verify your email address

**Step 2: Generate API Key**
1. Log into your dashboard
2. Navigate to "API Keys" section
3. Click "Generate New Key"
4. Copy the generated key (starts with `aipg_`)

**Step 3: Configure Worker Name**
Your worker name must follow this format: `YourName.YourWalletAddress`

Examples:
- `JohnDoe.0x1234567890abcdef1234567890abcdef12345678`
- `MyWorker.0xabcdef1234567890abcdef1234567890abcdef12`

> **💡 Pro Tip**: Use a descriptive name for your worker to easily identify it in the dashboard.

### Optional: Faster Download API Keys

**Hugging Face API Key (Recommended)**
1. Visit [huggingface.co](https://huggingface.co) and create an account
2. Go to Settings → Access Tokens
3. Create a new token with "Read" permissions
4. Add to your `.env` file as `HUGGING_FACE_API_KEY=your_token`

**CivitAI API Key (Optional)**
1. Visit [civitai.com](https://civitai.com) and create an account
2. Go to Account Settings → API Keys
3. Generate a new API key
4. Add to your `.env` file as `CIVITAI_API_KEY=your_token`

### API Key Troubleshooting

**❌ "Invalid API Key" Error**
- Verify the key is copied correctly (no extra spaces)
- Check if the key starts with `aipg_`
- Ensure your account is verified

**❌ "Worker Name Format Invalid" Error**
- Use format: `Name.WalletAddress`
- Ensure wallet address starts with `0x`
- Check for typos in the address

**❌ "Not Receiving Jobs" Error**
- Verify API key is valid at [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
- Check worker status in the dashboard
- Ensure models are "Hosting" (green status)

### Security Best Practices

**🔒 Protect Your API Keys**
- Never share your API keys publicly
- Don't commit `.env` files to version control
- Use different keys for different environments
- Rotate keys regularly

**🛡️ Environment File Security**
```bash
# Ensure .env file permissions are secure
chmod 600 .env

# Backup your configuration
cp .env .env.backup
```

---

<div align="center">

**🌟 Ready to turn your GPU into a money-making machine? Start earning AIPG tokens today!**

[![Get Started](https://img.shields.io/badge/Get%20Started-Dashboard%20AIPG-blue?style=for-the-badge)](https://dashboard.aipowergrid.io)

</div>
