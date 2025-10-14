# AI Power Grid - ComfyUI Bridge Worker

Turn your GPU into an AI processing node and earn AIPG tokens.

## Quick Start

### 1. Get Your API Key
Visit [dashboard.aipowergrid.io](https://dashboard.aipowergrid.io) and create a free account to get your API key.

### 2. Install Requirements
- **Docker** with **NVIDIA Container Toolkit** installed
- **NVIDIA GPU** with at least 6GB VRAM

> **Coming Soon**: AMD ROCm support for RX 7000 series and newer GPUs

### 3. Set Up the Worker
```bash
git clone <repository-url>
cd comfy-bridge
cp env.example .env
```

Edit `.env` and add your information:
```bash
GRID_API_KEY=your_api_key_here
GRID_WORKER_NAME=MyWorker.YourWalletAddress
```

### 4. Start the Worker
```bash
docker-compose up -d
```

### 5. Configure Models
Open [http://localhost:5000](http://localhost:5000) in your browser:
1. Select models that fit your GPU
2. Download the models
3. Click "Start Hosting"

**You're now earning rewards!**

---

## GPU Requirements

| Model Type | VRAM Needed | Examples |
|------------|-------------|----------|
| SD 1.5 | 6GB | Realistic Vision, Deliberate |
| SDXL | 8GB | SDXL 1.0, Juggernaut XL |
| Video (5B) | 24GB | wan2.2_ti2v_5B |
| Video (14B) | 96GB | wan2.2-t2v-a14b |

## Troubleshooting

**Can't see my GPU?**
- Run `nvidia-smi` in your terminal to verify your GPU is detected
- Make sure NVIDIA Container Toolkit is installed

**Models won't download?**
- Check your internet connection
- Verify your API key in the `.env` file

**Not receiving jobs?**
- Confirm models show "Hosting" status (green) in the UI
- Check your worker name format: `Name.WalletAddress`
- Verify your API key is valid

**View logs:**
```bash
docker-compose logs -f comfy-bridge
```

## Optional: Faster Downloads

Add these to your `.env` file for faster model downloads:
```bash
HUGGING_FACE_API_KEY=your_hf_token
CIVITAI_API_KEY=your_civitai_token
```

## Support

- **Documentation**: [aipowergrid.io](https://aipowergrid.io)
- **Community**: Join our Discord
- **Issues**: Report bugs on GitHub
