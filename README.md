# ComfyUI Bridge for AI Power Grid

Connect your local ComfyUI installation to the AI Power Grid network and run it as a distributed image generation worker.

> **🚀 New to Docker?** See [DOCKER.md](DOCKER.md) for the easiest deployment method!

---

## 🚀 Overview

- **Bridge**: Receives image-generation jobs from AI Power Grid.  
- **Worker**: Executes jobs via your local ComfyUI instance.  
- **Return**: Uploads generated images back to the network.  

This allows you to contribute GPU cycles to a decentralized AI rendering network while leveraging your local ComfyUI setup.

---

## 🎯 Features

- Auto-detects installed ComfyUI model checkpoints and maps them to AI Power Grid model names.  
- Customizable: override advertised models via `GRID_MODEL` (supports comma-separated lists).  
- Workflow templating: use your own ComfyUI `.json` workflow files.  
- Async, multi-threaded job polling and processing.  

---

## 🛠 Prerequisites

1. **Python 3.9+**  
2. **ComfyUI** running locally (default: `http://127.0.0.1:8000`).  
3. **AI Power Grid** account + API key: https://aipowergrid.io/register  

---

## 📦 Installation

```bash
# 1. Clone the repo
git clone https://github.com/youruser/comfy-bridge.git
cd comfy-bridge

# 2. Create & activate a virtual environment
python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

# 3. Install dependencies
pip install -e .
````

---

## ⚙️ Configuration

Copy the example `.env` and adjust values:

```ini
# .env
GRID_API_KEY=your_powergrid_api_key          # required
GRID_WORKER_NAME=MyComfyWorker.APIG_Wallet   # optional
COMFYUI_URL=http://127.0.0.1:8000            # optional
GRID_API_URL=https://api.aipowergrid.io/api  # optional
GRID_NSFW=false                              # allow NSFW? true/false
GRID_THREADS=2                               # concurrent jobs
GRID_MAX_PIXELS=1048576                      # max output resolution (pixels)
GRID_MODEL=stable_diffusion, Flux.1-Krea-dev Uncensored (fp8+CLIP+VAE)  # comma-separated model names
WORKFLOW_FILE=my_workflow.json               # ComfyUI JSON export template
```

* **`GRID_MODEL`** supports one or more model keys (comma-separated). If unset, the bridge auto-detects from your ComfyUI checkpoints.
* **`WORKFLOW_FILE`** points to a JSON workflow in your `workflows/` directory.

---

## ▶️ Running the Bridge

Start your ComfyUI web server, then:

```bash
# Via CLI module
python -m comfy_bridge.cli
```

Or directly (legacy):

```bash
start_bridge.py
```

The bridge will:

1. Register as a worker with AI Power Grid.
2. Poll for jobs every few seconds.
3. Render in ComfyUI.
4. Submit results back to the network.

---

## 🐳 Docker (Recommended)

The easiest way to deploy ComfyUI Bridge is using Docker with integrated ComfyUI.

### Quick Start

```bash
# 1. Copy environment file and configure
cp env.example .env
# Edit .env and add your GRID_API_KEY

# 2. Start with Docker Compose (includes ComfyUI)
docker-compose up -d

# 3. View logs
docker-compose logs -f
```

**That's it!** ComfyUI and the bridge will start automatically.

### What's Included

✅ **ComfyUI** - Pre-installed and auto-configured  
✅ **GPU Support** - CUDA 12.1 with PyTorch  
✅ **Auto-Start** - ComfyUI starts first, bridge connects automatically  
✅ **Persistent Storage** - Models and outputs saved to Docker volumes  
✅ **Health Checks** - Automatic monitoring and restart

### Accessing ComfyUI

- **API**: http://localhost:8188
- **Web UI**: http://localhost:8000 (optional)

See [DOCKER.md](DOCKER.md) for configuration, troubleshooting, and advanced features

---

## 🐳 Legacy Docker Setup

If you're running ComfyUI separately:

**Linux** (host networking):
```bash
docker run --rm --network host --env-file .env comfy-bridge
```

**macOS/Windows** (using `host.docker.internal`):
```bash
docker run --rm \
  -v "$(pwd)/workflows:/app/workflows" \
  --env-file .env \
  -e COMFYUI_URL=http://host.docker.internal:8000 \
  comfy-bridge
```

---


## 🐞 Troubleshooting

### Quick Diagnostics

Run the configuration checker to identify common issues:

```bash
python check_config.py
```

This checks your configuration, API key, ComfyUI connection, and workflow files.

### Enhanced Startup

Use the enhanced startup script for better logging and error handling:

```bash
python start_bridge.py
```

### Common Issues

* **Jobs stuck in waiting queue?** The bridge may not be advertising the correct models. Check startup logs for `📢 Advertising X models` and ensure video models like `wan2_2_t2v_14b` are listed.

* **No jobs found?** Check `Advertising models:` log; ensure `GRID_MODEL` is set or your checkpoints match default mappings.

* **400 Bad Request**: unrecognized models—verify model key names or adjust `GRID_MODEL`.

* **ComfyUI unreachable**: confirm `COMFYUI_URL` and that the server is running.

* **API auth errors**: verify `GRID_API_KEY` and network access.

### Enhanced Logging

The bridge now provides detailed startup information:

```
[INFO] 🚀 ComfyUI Bridge starting...
[INFO] 📋 Built workflow map with 10 models:
[INFO]   wan2_2_t2v_14b -> wan2.2-t2v-a14b.json
[INFO] 📢 Advertising 10 models to AI Power Grid:
[INFO]   1. wan2_2_t2v_14b
[INFO] 🔄 Polling for jobs (attempt #1)...
[INFO] ✓ Got job abc123 for model wan2_2_t2v_14b
```

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgements

* **AI Power Grid** ([https://aipowergrid.io](https://aipowergrid.io)) - For the API
* **ComfyUI** ([https://github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)) - For the local image generation backend
* **httpx**, **aiohttp** for async HTTP operations ❤️
