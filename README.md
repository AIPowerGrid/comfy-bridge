<div align="center">

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     █████╗ ██╗██████╗  ██████╗ ██╗    ██╗███████╗██████╗      ║
║    ██╔══██╗██║██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗     ║
║    ███████║██║██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝     ║
║    ██╔══██║██║██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗     ║
║    ██║  ██║██║██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║     ║
║    ╚═╝  ╚═╝╚═╝╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝     ║
║                                                               ║
║     ██████╗ ██████╗ ██╗██████╗                                ║
║    ██╔════╝██╔═══██╗██║██╔══██╗                               ║
║    ██║     ██║   ██║██║██║  ██║                               ║
║    ██║     ██║   ██║██║██║  ██║                               ║
║    ╚██████╗╚██████╔╝██║██████╔╝                               ║
║     ╚═════╝ ╚═════╝ ╚═╝╚═════╝                                ║
║                                                               ║
║     Turn Your GPU Into a Money-Making Machine                ║
║     and Give Back to the Community                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&style=for-the-badge)](https://www.docker.com/)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-GPU-green?logo=nvidia&style=for-the-badge)](https://www.nvidia.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python&style=for-the-badge)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)](https://dashboard.aipowergrid.io)

**🎨 Generate AI art and videos while earning AIPG tokens!**

---

</div>

## 🚀 Quick Start (30 Seconds)

**Just want to get started? Here's all you need:**

1. **Get your API key** from [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. **Copy `env.example` to `.env`** and add your API key
3. **Double-click the start script** for your OS:
   - **Windows**: `start-worker.bat`
   - **Mac/Linux**: `start-worker.sh`
4. **Open http://localhost:5000** and select models
5. **Click "Start Hosting"** → You're earning! 💰

That's it! Your GPU is now making money while you sleep.

---

## 💰 Why Run This Worker?

### **Earn Passive Income**
- **Get paid in AIPG tokens** for every AI generation your GPU processes
- **Work runs 24/7** - earn money even when you're not using your computer
- **No technical skills needed** - just click start and forget it

### **Support the AI Revolution**
- Help power the decentralized AI network
- Make AI generation accessible to everyone
- Be part of the future of AI infrastructure

### **Easy Setup, Zero Maintenance**
- **One-click start** - no complex configuration
- **Automatic updates** - always running the latest version
- **Web interface** - manage everything from your browser

---

## 🎁 What You Get

| Benefit | Description |
|---------|-------------|
| 💵 **Earn Tokens** | Get paid for every AI image/video generation |
| 🎨 **Free AI Tools** | Access to powerful AI models at no cost |
| 🌐 **Decentralized** | Support the open AI network |
| 🔒 **Secure** | Your API keys stay private, never shared |
| 📊 **Dashboard** | Track earnings and performance in real-time |

---

## 📋 Requirements

The start scripts automatically check these requirements:

- **Docker Desktop** installed and running
- **50GB+ free disk space** (for models and Docker images)
- **NVIDIA GPU** with 6GB+ VRAM (or AMD GPU with ROCm)
- **8GB+ RAM** recommended

If requirements are not met, the scripts will guide you through installation.

---

## 🚀 Detailed Setup Guide

### Step 1: Get Your API Key 🔑

1. Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
2. Sign up (it's free!)
3. Go to "API Keys" → Generate new key
4. Copy the key (starts with `aipg_`)

### Step 2: Configure Your Worker ⚙️

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

> 💡 **Worker Name Format**: `YourName.YourWalletAddress`  
> Example: `JohnDoe.0x1234567890abcdef1234567890abcdef12345678`

### Step 3: Start the Worker 🎬

**Windows:**
- Double-click `start-worker.bat`

**Mac/Linux:**
- Run: `./start-worker.sh`
- Or: `chmod +x start-worker.sh && ./start-worker.sh`

The script will automatically:
- Check disk space (50GB minimum)
- Verify Docker is installed
- Ensure Docker is running
- Validate configuration file

### Step 4: Select Models 🎨

1. Open **http://localhost:5000** in your browser
2. Browse available models (filter by your GPU's VRAM)
3. Click **Download** for models you want to host
4. Wait for downloads to complete
5. Click **"Start Hosting"** → You're earning! 🎉

---

## 📊 Monitor Your Earnings

- **Dashboard**: [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)
- **Local UI**: http://localhost:5000
- **View Logs**: `docker-compose logs -f`

---

## 🛠️ Troubleshooting

**Worker won't start?**
- Make sure Docker Desktop is running
- Check that `.env` file exists and has your API key
- Run `docker-compose logs` to see error messages

**Not receiving jobs?**
- Verify models show "Hosting" status (green) in the UI
- Check your API key is valid at dashboard.aipowergrid.io
- Ensure worker name format is correct: `Name.WalletAddress`

**GPU not detected?**
- Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- Run `nvidia-smi` to verify GPU is detected
- Restart Docker Desktop

**Need more help?**
- Check logs: `docker-compose logs -f`
- Visit our [Discord community](https://discord.gg/aipowergrid)
- Read the [full documentation](https://aipowergrid.io)

---

## 🎮 GPU Requirements

| Model Type | VRAM Needed | What It Does |
|------------|-------------|--------------|
| **SD 1.5** | 6GB | General images |
| **SDXL** | 8GB | High-res images |
| **Flux** | 12GB | Advanced images |
| **Video (5B)** | 16GB | Short videos |
| **Video (14B)** | 32GB | High-quality videos |

> 💡 **Start small**: Begin with SD 1.5 models, then upgrade as you expand!

---

## 🔄 Updates & Maintenance

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

**View logs:**
```bash
docker-compose logs -f
```

---

## 📚 Advanced Configuration

### Optional: Faster Downloads

Add these to your `.env` for faster model downloads:

```bash
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

### Optional: Custom Ports

Edit `docker-compose.yml` to change ports if needed.

---

## 🏗️ Architecture

This worker runs ComfyUI (powerful AI generation engine) and connects it to the AI Power Grid network. When someone requests an AI generation, your GPU processes it and you get paid!

**Components:**
- **ComfyUI**: The AI generation engine
- **Bridge**: Connects to AI Power Grid network
- **Management UI**: Web interface for easy management

---

## 📖 Additional Resources

- **📚 Full Docs**: [aipowergrid.io](https://aipowergrid.io)
- **💬 Community**: Join our Discord
- **🐛 Report Issues**: GitHub Issues
- **📊 Dashboard**: [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io)

---

<div align="center">

**Made with ❤️ by [ameli0x](https://github.com/ameli0x) and [half](https://github.com/half)**

**🌟 Ready to turn your GPU into a money-making machine?**

[![Get Started](https://img.shields.io/badge/Get%20Started-Dashboard%20AIPG-blue?style=for-the-badge&logo=rocket)](https://dashboard.aipowergrid.io)

**Questions?** Join our [Discord](https://discord.gg/aipowergrid) community!

</div>
