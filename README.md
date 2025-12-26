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
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&style=for-the-badge)](https://nodejs.org/en/download)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)](https://dashboard.aipowergrid.io)

**🎨 Generate AI art and videos while earning AIPG tokens!**

> ⏱️ **Heads up:** The very first build takes **45–60 minutes** (Docker images, model cache, desktop app). Let it run once; every restart after that is usually under two minutes.

---
=======
- Docker Desktop (Free version is fine) (https://www.docker.com/products/docker-desktop/)
- Node.js (https://nodejs.org/en/download)
- An API key from [AI Power Grid](https://dashboard.aipowergrid.io)
- An API key from [Huggingface](https://huggingface.co/settings/tokens) (once logged in)
- An API key from [Civitai](https://civitai.com/user/account) (once logged in)

</div>

## 🚀 Quick Start

**Get up and running in under 2 minutes - everything happens automatically!**

1. 🔑 Get your API key from [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. ⚙️ Copy `env.example` to `.env` and add your API key
3. ▶️ **Right-click** and **"Run as Administrator"** the start script:
   - **Windows**: `start-worker.bat` (right-click → Run as Administrator)
   - **Mac/Linux**: `sudo ./start-worker.sh`
4. ⏳ **Plan 45–60 minutes for the very first run.** Docker pulls, dependency installs, model downloads, and the desktop app build all happen automatically—later launches are fast.
5. ✨ **That's it!** The script automatically:
   - ✅ Checks all requirements (disk space, Docker, etc.)
   - ✅ Starts Docker containers
   - ✅ Downloads models listed in `.env` during image build
   - ✅ Builds the desktop app automatically
   - ✅ Cleans up stale Docker volumes so upgrades stay reliable
6. 🖥️ **Desktop app** is built automatically and available in `management-ui-nextjs/dist/`
7. 🎨 Open the desktop app OR http://localhost:5000 in your browser
8. 💰 Click "Start Hosting" → You're earning!

> 💡 **Desktop App:** The Electron app is built automatically during Docker build - no Node.js needed on your host! Find it in `management-ui-nextjs/dist/` after building.

> ⚡ **Pro Tip:** Everything happens automatically - Docker builds the desktop app, downloads models, and sets everything up. Just run the script and you're done!

---

## 💰 Why Run This Worker?

### Turn Idle Time Into Income 💵
Your GPU sits idle most of the time. Why not put it to work? You earn AIPG tokens just by having the worker running - even while you sleep!

### Simple Setup, Zero Hassle ⚡
- **One-click start** - no complex configuration needed
- **Web UI** - manage everything from your browser
- **Automatic updates** - always running the latest version
- **24/7 operation** - set it and forget it

### Power the Future of AI 🌐
Join thousands of GPU owners helping build a decentralized AI network. Make AI generation accessible to everyone while earning rewards.

---

## 🎁 What You Get

| Benefit | What It Means |
|---------|---------------|
| 💵 **Earn Tokens** | Get paid in AIPG just for running the worker |
| 🎨 **Free AI Access** | Use powerful AI models without paying |
| 🔒 **Secure** | Your API keys stay private, never shared |
| 📊 **Real-time Dashboard** | Track earnings and performance live |
| 🌐 **Decentralized** | Support the open AI network |
| ⚡ **Easy Management** | Web UI and desktop app make everything simple |
| 🖥️ **Desktop App** | Native desktop application built automatically during Docker build |

---

## 🖥️ Desktop App (Electron)

**The Electron desktop app is automatically built during Docker image build!** No manual setup required - it's ready to use right after `docker-compose build`.

### ✨ Automatic Build (Recommended)

When you run `docker-compose build`, the Electron desktop app is built automatically:

```bash
# Build everything including Electron app
docker-compose build

# The built app is available at:
# management-ui-nextjs/dist/
```

**What you get:**
- ✅ **Built automatically** - No manual steps needed
- ✅ **Ready to use** - Available in `management-ui-nextjs/dist/` after build
- ✅ **Platform-specific** - Built for your container platform (Linux)
- ✅ **Skip if needed** - Set `BUILD_ELECTRON=false` to skip

**To skip Electron build:**
```bash
# Option 1: Environment variable
BUILD_ELECTRON=false docker-compose build

# Option 2: Add to .env file
echo "BUILD_ELECTRON=false" >> .env
```

### 📦 Finding Your Built App

After building, check the `dist/` directory:
- **Linux**: `dist/linux-unpacked/` or `dist/*.AppImage` or `dist/*.deb`
- **Windows/Mac**: Build on those platforms or use manual build scripts below

### 🛠️ Manual Build (Optional)

If you need to build manually outside Docker or for a different platform:

**Prerequisites:**
- Node.js 18+ installed
- Docker containers running (app connects to `http://localhost:5000`)

**Quick build:**
```bash
cd management-ui-nextjs
npm install
npm run electron:build    # Production build
# OR
npm run electron:pack     # Portable build (Windows)
```

**Development mode:**
```bash
npm run electron:dev      # Auto-reloads on code changes
```

### 🚀 Launching the App

**From Docker build:**
- Navigate to `management-ui-nextjs/dist/`
- Run the executable for your platform
- App connects to `http://localhost:5000` automatically

**Features:**
- ✅ Native window controls and system integration
- ✅ No browser needed - standalone application
- ✅ Better performance and offline capability
- ✅ Same functionality as web interface

---

## 📋 Requirements

### Software (install once)

- ✅ **Docker Desktop** – [Download for Windows / macOS](https://www.docker.com/products/docker-desktop/) (Linux users install Docker Engine from your distro repos). Docker runs ComfyUI, Python, and every dependency in containers, so you never touch those directly.
- ✅ **Node.js 18+** – [Download installers](https://nodejs.org/en/download). We use Node to build the AI Power Grid desktop app automatically.

> 💡 The start scripts verify both apps are installed/running and walk you through fixes if something is missing.

### Hardware & Space (automatically checked)

- 💾 **50GB+ free disk space** (for Docker images + models)
- 🖥️ **NVIDIA GPU** with 6GB+ VRAM (or comparable AMD ROCm card)
- 🧠 **8GB+ system RAM** recommended

If a check fails, the script pauses with a friendly message so you can address it and re-run.

---

## 📖 Detailed Setup Guide

### Step 1: Get Your API Key 🔑

1. Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Sign up (it's free!)
3. Go to **"API Keys"** → Generate new key
4. Copy the key (starts with `aipg_`)

### Step 2: Configure ⚙️

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

Add these two lines (replace with your actual values):
```bash
GRID_API_KEY=aipg_your_key_here
GRID_WORKER_NAME=YourName.YourWalletAddress
```

> 📝 **Worker Name Format**: `YourName.YourWalletAddress`  
> Example: `JohnDoe.0x1234567890abcdef1234567890abcdef12345678`

### Step 3: Start the Worker ▶️

**Windows:**
- Double-click `start-worker.bat`

**Mac/Linux:**
- Run: `./start-worker.sh`
- Or: `chmod +x start-worker.sh && ./start-worker.sh`

The script automatically:
- ✅ Checks disk space (50GB minimum)
- ✅ Verifies Docker is installed
- ✅ Ensures Docker is running
- ✅ Validates your configuration
- ✅ Builds the desktop app (if Node.js is installed)
- ✅ Creates a desktop shortcut for easy access

### Step 4: Select Models 🎨

> 🔗 **Blockchain Model Registry**: All models are registered and validated through the ModelVault smart contract on Base Mainnet. This ensures authenticity, proper attribution, and trustless model discovery.

**Option A: Use the Desktop App (Recommended - Created Automatically!)**
1. Look for **"AI Power Grid Manager"** shortcut on your desktop
2. Double-click to launch (no browser needed!)
3. Browse available models (filter by your GPU's VRAM)
   - All models are verified on the blockchain ✅
   - Only registered models can be downloaded and hosted
4. Click **Download** for models you want to host
5. Wait for downloads to complete
6. Click **"Start Hosting"** → You're earning! 🎉

**Option B: Use the Web Interface**
1. Open **http://localhost:5000** in your browser
2. Browse available models (filter by your GPU's VRAM)
   - All models are verified on the blockchain ✅
   - Only registered models can be downloaded and hosted
3. Click **Download** for models you want to host
4. Wait for downloads to complete
5. Click **"Start Hosting"** → You're earning! 🎉

> 💡 **Note:** The desktop app is automatically built and a shortcut is created when you run the start script. If the shortcut wasn't created, you can still use the web interface!

> 🔐 **Security:** All model information comes from the blockchain - no centralized server controls which models are available. This ensures transparency and prevents censorship.

---

## 📊 Monitor Your Earnings

Track your progress in real-time:

- **🖥️ Desktop App**: Desktop shortcut created automatically! Launch "AI Power Grid Manager" from your desktop (no browser needed!)
- **🌐 Dashboard**: [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io) - View earnings, stats, and history
- **💻 Web UI**: http://localhost:5000 - Manage models and monitor jobs in your browser
- **📝 View Logs**: `docker-compose logs -f` - See detailed activity

---

## 🛠️ Troubleshooting

### Worker Won't Start ❌

**Check these first:**
- ✅ Docker Desktop is running (look for whale icon in system tray)
- ✅ `.env` file exists with your API key
- ✅ Check logs: `docker-compose logs` for specific errors

**Common fixes:**
- Restart Docker Desktop
- Verify port 5000 or 8188 isn't already in use
- Ensure you have enough disk space (50GB+)

### Not Receiving Jobs? 🔍

**Verify these:**
- ✅ Models show **"Hosting"** status (green) in the UI
- ✅ API key is valid at dashboard.aipowergrid.io
- ✅ Worker name format is correct: `Name.WalletAddress`
- ✅ Worker is online (check dashboard)

**Still not working?**
- Check logs: `docker-compose logs -f`
- Verify your GPU meets model requirements
- Ensure models finished downloading completely

### GPU Not Detected? 🎮

**For NVIDIA GPUs:**
1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Run `nvidia-smi` to verify GPU is detected
3. Restart Docker Desktop
4. Check logs: `docker-compose logs -f`

**For AMD GPUs:**
- Ensure ROCm is properly installed
- Check Docker supports your GPU model

### TypeScript/Build Errors? 🔧

If you see errors about missing modules or TypeScript types when working with the management UI:
```bash
cd management-ui-nextjs
npm install
```
This installs all required dependencies and type definitions.

### Need More Help? 💬

- 📝 **Logs**: `docker-compose logs -f` - See what's happening
- 💬 [Discord](https://discord.gg/aipowergrid) - Get help from the community
- 📚 [Documentation](https://aipowergrid.io) - Full technical docs

---

## 🎮 GPU Requirements

| Model Type | VRAM Needed | What It Does |
|------------|-------------|--------------|
| **SD 1.5** | 6GB | General images, fastest |
| **SDXL** | 8GB | High-resolution images |
| **Flux** | 12GB | Advanced, high-quality images |
| **Video (5B)** | 16GB | Short videos (5-10 seconds) |
| **Video (14B)** | 32GB | High-quality videos |

> 💡 **New to GPU hosting?** Start with SD 1.5 models - they're the most popular and work great on entry-level GPUs!

---

## 🔄 Common Commands

**Update to latest version:**
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

**Stop the worker:**
```bash
docker-compose down
```

**Start the worker:**
```bash
docker-compose up -d
```

**View live logs:**
```bash
docker-compose logs -f
```

**Restart after changes:**
```bash
docker-compose restart
```

---

## ⚙️ Advanced Configuration

### Faster Model Downloads 🚀

Add these to your `.env` for faster downloads:
```bash
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

> 💡 These API keys are optional but can significantly speed up model downloads from Hugging Face and Civitai.

### Download Models During Build 🏗️

**Models listed in your `.env` file are automatically downloaded during the Docker image build!**

This means:
- ✅ Models are ready immediately when containers start (no waiting at runtime)
- ✅ Faster container startup times
- ✅ Models are baked into the image for consistent deployments

**How it works:**
1. Add models to your `.env` file:
   ```bash
   GRID_MODEL=FLUX.1-dev,SDXL,SD-1.5
   # OR
   WORKFLOW_FILE=flux.1_krea_dev.json,sdxl1.json
   ```

2. Rebuild the Docker image:
   ```bash
   docker-compose build --no-cache comfy-bridge
   ```

3. Models will be downloaded during the build process

**Note:** If you add models to `.env` after the image is built, they'll be downloaded at runtime when the container starts. To download during build, rebuild the image with the updated `.env` file.

**Build-time vs Runtime downloads:**
- **Build-time**: Models are in the Docker image, faster container startup
- **Runtime**: Models are downloaded when container starts (if not in image or .env changed)
- Both methods work - choose based on your workflow!

### Blockchain Model Registry 🔗

**All models are registered and validated through the ModelVault smart contract on Base Mainnet.**

The blockchain is the **single source of truth** for:
- ✅ Model discovery and availability
- ✅ Model authenticity and verification  
- ✅ Download URLs and file hashes
- ✅ Model constraints (steps, CFG, samplers)

**Configuration (already set by default):**
```bash
MODELVAULT_ENABLED=true                        # Enable blockchain registry
MODELVAULT_RPC_URL=https://mainnet.base.org    # Base Mainnet RPC
MODELVAULT_CONTRACT=0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609  # Contract address
```

**Benefits:**
- 🔐 **Trustless**: No central authority controls which models are available
- ✅ **Verified**: All models are registered on-chain with cryptographic hashes
- 🌐 **Transparent**: Anyone can verify model registration and details
- 🚫 **Censorship-resistant**: No single entity can remove models from the registry

### Wallet Connect Configuration 🔗

The Management UI supports Web3 wallet connections for blockchain features. A default WalletConnect project ID is provided, but you can get your own free project ID:

1. Visit https://cloud.walletconnect.com
2. Create a free account and new project
3. Add to your `.env`:
   ```bash
   NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_project_id
   ```

### Custom Ports 🔌

Edit `docker-compose.yml` to change ports if needed:
- Default: Management UI on port `5000`, ComfyUI on port `8188`
- Change if these ports conflict with other services

---

## 🏗️ How It Works

This worker runs **ComfyUI** (powerful AI generation engine) and connects it to the **AI Power Grid** network. You earn AIPG tokens just by keeping the worker running and hosting models!

**Components:**
- 🎨 **ComfyUI** - The AI generation engine that processes jobs
- 🌉 **Bridge** - Connects your worker to the AI Power Grid network
- 💻 **Management UI** - Web interface for easy model and job management

**The Flow:**
1. Your worker connects to the network
2. Jobs come in and your GPU processes them
3. You earn AIPG tokens for keeping the worker online
4. Payments are made every hour on the 20 minute mark! 💰

---

## 📚 Additional Resources

- 📖 [Full Documentation](https://aipowergrid.io) - Complete technical docs
- 💬 [Discord Community](https://discord.gg/aipowergrid) - Get help, share tips
- 📊 [Dashboard](https://dashboard.aipowergrid.io) - Track earnings and manage account
- 🐛 [Report Issues](https://github.com/AIPowerGrid/comfy-bridge/issues) - Found a bug?

---

## ❓ Frequently Asked Questions

### 💰 Earning & Payments

**Q: How much can I earn?**  
A: Earnings depend on your GPU, models hosted, and network demand. Higher-end GPUs hosting popular models typically earn more. Check the dashboard for current rates.

**Q: How do I get paid?**  
A: You earn AIPG tokens automatically just by having the worker running. No need to process jobs - just keep it online!

**Q: When do I get paid?**  
A: Payments are made automatically every hour on the 20 minute mark (e.g., 1:20, 2:20, 3:20). Check your dashboard to see your earnings.

**Q: Can I run this on multiple GPUs?**  
A: Yes! Each GPU can run its own worker instance. Just use different worker names and ensure each has enough resources.

### 🎮 GPU & Hardware

**Q: Do I need a high-end GPU?**  
A: No! Entry-level GPUs (6GB VRAM) can run SD 1.5 models. Higher-end GPUs can run more advanced models and earn more.

**Q: Can I use my GPU while the worker runs?**  
A: Yes, but it may slow down both. The worker uses GPU resources, so gaming or other GPU-intensive tasks may impact performance.

**Q: Will this damage my GPU?**  
A: No. The worker runs at normal operating temperatures. Modern GPUs are designed for 24/7 operation. Monitor temperatures if concerned.

**Q: Can I use an AMD GPU?**  
A: Yes! AMD GPUs with ROCm support work. Setup may differ slightly - check the documentation for AMD-specific instructions.

### ⚙️ Setup & Configuration

**Q: Do I need technical knowledge?**  
A: No! The one-click scripts handle everything. Basic computer skills are enough.

**Q: How long does setup take?**  
A: About 2-5 minutes for initial setup, plus model download time (varies by model size and internet speed).

**Q: Can I change models later?**  
A: Yes! Use the web UI at http://localhost:5000 to download new models or stop hosting current ones anytime.

**Q: Do I need to keep my computer on?**  
A: Yes, the worker needs your computer running. Many users run it 24/7 on dedicated machines or when idle.

### 🔒 Security & Privacy

**Q: Is my API key safe?**  
A: Yes! Your API key stays on your machine and is never shared. Only you have access to it.

**Q: Can others access my GPU?**  
A: No. Only jobs from the AI Power Grid network are processed. You control which models to host.

**Q: What data is collected?**  
A: Only worker status and uptime metrics (for payments). No personal data or generated content is stored.

### 🐛 Troubleshooting

**Q: Worker won't start**  
A: Check Docker is running, `.env` file exists, and you have enough disk space. Run `docker-compose logs` for details.

**Q: Not receiving jobs**  
A: Verify models show "Hosting" status (green), API key is valid, and worker name format is correct.

**Q: Jobs failing**  
A: Check GPU has enough VRAM for the model, logs for errors, and ensure models downloaded completely.

**Q: Slow performance**  
A: Ensure no other GPU-intensive apps are running, check GPU temperatures aren't throttling, and verify Docker has GPU access.

### 🌐 Network & Connectivity

**Q: Do I need fast internet?**  
A: Moderate speed is fine. Faster internet helps with model downloads and uploading results faster.

**Q: Can I run this offline?**  
A: No, you need internet to receive jobs and upload results. The worker connects to the AI Power Grid network.

**Q: What ports are used?**  
A: Port 5000 (Management UI) and 8188 (ComfyUI). These can be changed in `docker-compose.yml` if needed.

### 📊 Models & Performance

**Q: Which models should I host?**  
A: Start with SD 1.5 (most popular). Then try SDXL or Flux if your GPU supports it. Video models require more VRAM.

**Q: How many models can I host?**  
A: As many as your disk space allows. Each model needs to be downloaded and stored. Start with 2-3 popular models.

**Q: Can I test models before hosting?**  
A: Yes! Use the ComfyUI interface at http://localhost:8188 to test models before enabling hosting.

**Q: Why are some models not available?**  
A: Models may require more VRAM than your GPU has, or may not be supported yet. Check GPU requirements table above.

---

<div align="center">

**Made with ❤️ by [ameli0x](https://github.com/ameli0x) and [half](https://github.com/half)**

[![Get Started](https://img.shields.io/badge/Get%20Started-Dashboard%20AIPG-blue?style=for-the-badge&logo=rocket)](https://dashboard.aipowergrid.io)

[💬 Discord](https://discord.gg/aipowergrid) | [📚 Documentation](https://aipowergrid.io)

**Ready to turn your GPU into a money-making machine?** 🚀

- [AI Power Grid](https://aipowergrid.io/) for the API
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) for the local image generation backend 
