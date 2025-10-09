# AI Power Grid - ComfyUI Bridge Worker

Transform your GPU into an AI Power Grid node. This worker connects ComfyUI to the AI Power Grid network, allowing you to earn rewards by processing AI generation jobs.

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd comfy-bridge
   cp env.example .env
   ```

2. **Configure Your Worker**
   - Edit `.env` file with your API keys
   - Visit http://localhost:5000 to select models based on your GPU

3. **Start the Worker**
   ```bash
   docker-compose up -d
   ```

4. **Access Management UI**
   - Open http://localhost:5000
   - Configure Grid connection and select models
   - Download and start hosting to earn rewards

## 📋 Requirements

- **GPU**: NVIDIA GPU with 6GB+ VRAM (24GB+ recommended)
- **Software**: Docker with NVIDIA Container Toolkit
- **API Keys**: AI Power Grid API key (free from dashboard.aipowergrid.io)

## ⚙️ Configuration

### Essential Settings (.env file)

```bash
# Required: Get from https://dashboard.aipowergrid.io
GRID_API_KEY=your_api_key_here

# Worker identity (format: WorkerName.WalletAddress)
GRID_WORKER_NAME=MyWorker.WalletAddress123

# Model selection (configure via web UI)
WORKFLOW_FILE=

# Optional: For faster model downloads
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

### GPU Requirements by Model Type

| Model Type | VRAM Required | Example Models |
|------------|---------------|----------------|
| Text-to-Image (SD 1.5) | 6GB | Realistic Vision, Deliberate |
| Text-to-Image (SDXL) | 8GB | SDXL 1.0, Juggernaut XL |
| Text-to-Video (Wan 5B) | 24GB | wan2.2_ti2v_5B |
| Text-to-Video (Wan 14B) | 96GB | wan2.2-t2v-a14b |

## 🎯 How It Works

1. **Model Selection**: Choose models compatible with your GPU via web UI
2. **Download**: Models download automatically to persistent storage
3. **Hosting**: Your worker advertises available models to the network
4. **Earning**: Process jobs and earn AIPG tokens automatically

## 🖥️ Management Interface

Access the web UI at http://localhost:5000 to:

- **GPU Detection**: See your GPU capabilities and VRAM usage
- **Model Management**: Browse, download, and host models
- **Configuration**: Set up Grid connection and API keys
- **Monitoring**: Track hosting status and earnings

## 📁 File Structure

```
comfy-bridge/
├── docker-compose.yml          # Main orchestration
├── .env                        # Your configuration
├── workflows/                  # ComfyUI workflow templates
├── persistent_volumes/         # Your downloaded models
└── management-ui-nextjs/       # Web interface
```

## 🔧 Troubleshooting

### Common Issues

**GPU Not Detected**
- Ensure NVIDIA Container Toolkit is installed
- Check `nvidia-smi` works in your system

**Models Not Downloading**
- Verify API keys in .env file
- Check internet connection and firewall

**Worker Not Receiving Jobs**
- Confirm GRID_API_KEY is valid
- Ensure models are hosted (green status in UI)
- Check worker name format: `Name.WalletAddress`

### Logs
```bash
# View worker logs
docker-compose logs -f comfy-bridge

# View UI logs  
docker-compose logs -f management-ui
```

## 💰 Earning Rewards

- **Passive Income**: Earn while your GPU processes jobs
- **Automatic Payouts**: Rewards sent to your AIPG wallet
- **Performance Based**: More powerful GPUs = higher rewards
- **24/7 Operation**: Run continuously for maximum earnings

## 🆘 Support

- **Documentation**: Full docs at aipowergrid.io
- **Community**: Join our Discord for help
- **Issues**: Report bugs via GitHub issues

---

**Ready to start earning?** Run `docker-compose up -d` and visit http://localhost:5000! 🚀