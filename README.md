<div align="center">

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║            █████╗ ██╗██████╗  ██████╗                         ║
║           ██╔══██╗██║██╔══██╗██╔════╝                         ║
║           ███████║██║██████╔╝██║  ███╗                        ║
║           ██╔══██║██║██╔═══╝ ██║   ██║                        ║
║           ██║  ██║██║██║     ╚██████╔╝                        ║
║           ╚═╝  ╚═╝╚═╝╚═╝      ╚═════╝                         ║
║                                                               ║
║        Turn Your GPU Into a Money-Making Machine              ║
║        and Help Power the Community                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&style=for-the-badge)](https://www.docker.com/)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-GPU-green?logo=nvidia&style=for-the-badge)](https://www.nvidia.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python&style=for-the-badge)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)](https://dashboard.aipowergrid.io)

**Generate AI art and videos while earning AIPG tokens**

---

</div>

## Quick Start

1. Get your API key from [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Copy `env.example` to `.env` and add your API key
3. Run the start script:
   - **Windows**: Double-click `start-worker.bat`
   - **Mac/Linux**: Run `./start-worker.sh`
4. Open http://localhost:5000 and select models
5. Click "Start Hosting" to begin earning

---

## Why Run This Worker?

- **Earn AIPG tokens** for every AI generation your GPU processes
- **Runs 24/7** - earn while your computer is idle
- **Simple setup** - one script to start, web UI to manage
- **Help power** the decentralized AI network

---

## What You Get

- **Earn tokens** for every AI generation
- **Access to AI models** at no cost
- **Secure** - API keys stay private
- **Dashboard** to track earnings

---

## Requirements

The start scripts check these automatically:

- Docker Desktop installed and running
- 50GB+ free disk space
- NVIDIA GPU with 6GB+ VRAM (or AMD GPU with ROCm)
- 8GB+ RAM recommended

Scripts will guide you through installation if anything is missing.

---

## Detailed Setup

### Step 1: Get Your API Key

1. Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Sign up (it's free!)
3. Go to "API Keys" → Generate new key
4. Copy the key (starts with `aipg_`)

### Step 2: Configure

**Windows:**
```bash
copy env.example .env
notepad .env
```

**Mac/Linux:**
```bash
cp env.example .env
nano .env
```

Add these lines (replace with your values):
```bash
GRID_API_KEY=aipg_your_key_here
GRID_WORKER_NAME=YourName.YourWalletAddress
```

Worker name format: `YourName.YourWalletAddress`  
Example: `JohnDoe.0x1234567890abcdef1234567890abcdef12345678`

### Step 3: Start the Worker

**Windows:**
- Double-click `start-worker.bat`

**Mac/Linux:**
- Run: `./start-worker.sh`
- Or: `chmod +x start-worker.sh && ./start-worker.sh`

The script checks disk space, Docker installation, and configuration.

### Step 4: Select Models

1. Open http://localhost:5000 in your browser
2. Browse models (filter by your GPU's VRAM)
3. Click Download for models you want to host
4. Wait for downloads to complete
5. Click "Start Hosting" to begin earning

---

## Monitor Earnings

- Dashboard: [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
- Local UI: http://localhost:5000
- View logs: `docker-compose logs -f`

---

## Troubleshooting

**Worker won't start:**
- Ensure Docker Desktop is running
- Verify `.env` file exists with your API key
- Check logs: `docker-compose logs`

**Not receiving jobs:**
- Models must show "Hosting" status (green) in UI
- Verify API key at dashboard.aipowergrid.io
- Check worker name format: `Name.WalletAddress`

**GPU not detected:**
- Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- Run `nvidia-smi` to verify GPU detection
- Restart Docker Desktop

**More help:**
- Logs: `docker-compose logs -f`
- [Discord](https://discord.gg/aipowergrid)
- [Documentation](https://aipowergrid.io)

---

## GPU Requirements

| Model Type | VRAM Needed |
|------------|-------------|
| SD 1.5 | 6GB |
| SDXL | 8GB |
| Flux | 12GB |
| Video (5B) | 16GB |
| Video (14B) | 32GB |

Start with SD 1.5 models if you have limited VRAM.

---

## Commands

**Update:**
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

**Stop:** `docker-compose down`  
**Start:** `docker-compose up -d`  
**Logs:** `docker-compose logs -f`

---

## Advanced Configuration

**Faster downloads** - Add to `.env`:
```bash
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

**Custom ports** - Edit `docker-compose.yml` if needed.

---

## Architecture

Runs ComfyUI and connects to the AI Power Grid network. When someone requests a generation, your GPU processes it and you get paid.

**Components:**
- ComfyUI: AI generation engine
- Bridge: Connects to AI Power Grid network
- Management UI: Web interface for management

---

## Resources

- [Documentation](https://aipowergrid.io)
- [Discord](https://discord.gg/aipowergrid)
- [Dashboard](https://dashboard.aipowergrid.io)
- [GitHub Issues](https://github.com/AIPowerGrid/comfy-bridge/issues)

---

<div align="center">

**Made with ❤️ by [ameli0x](https://github.com/ameli0x) and [half](https://github.com/half)**

[![Get Started](https://img.shields.io/badge/Get%20Started-Dashboard%20AIPG-blue?style=for-the-badge&logo=rocket)](https://dashboard.aipowergrid.io)

[Discord](https://discord.gg/aipowergrid) | [Documentation](https://aipowergrid.io)

</div>
