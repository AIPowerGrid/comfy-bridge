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

**🎨 Generate AI art and videos while earning AIPG tokens!**

- Python 3.9+
- A running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) instance
- An API key from [AI Power Grid](https://dashboard.aipowergrid.io)

</div>

## 🚀 Quick Start

**Get up and running in under 2 minutes:**

1. 🔑 Get your API key from [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. ⚙️ Copy `env.example` to `.env` and add your API key
3. ▶️ Run the start script:
   - **Windows**: Double-click `start-worker.bat`
   - **Mac/Linux**: Run `./start-worker.sh`
4. 🎨 Open http://localhost:5000 and select models
5. 💰 Click "Start Hosting" → You're earning!

> ⚡ **Pro Tip:** The script automatically checks all requirements and guides you through setup!

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
| ⚡ **Easy Management** | Web UI makes everything simple |

---

## 📋 Requirements

The start scripts **automatically check** these for you:

- ✅ **Docker Desktop** installed and running
- ✅ **50GB+ free disk space** (for models and Docker images)
- ✅ **NVIDIA GPU** with 6GB+ VRAM (or AMD GPU with ROCm)
- ✅ **8GB+ RAM** recommended

> 💡 **Don't worry!** If anything is missing, the scripts guide you through installation step-by-step.

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

### Step 4: Select Models 🎨

1. Open **http://localhost:5000** in your browser
2. Browse available models (filter by your GPU's VRAM)
3. Click **Download** for models you want to host
4. Wait for downloads to complete
5. Click **"Start Hosting"** → You're earning! 🎉

---

## 📊 Monitor Your Earnings

Track your progress in real-time:

- **🌐 Dashboard**: [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io) - View earnings, stats, and history
- **💻 Local UI**: http://localhost:5000 - Manage models and monitor jobs
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
