# ComfyUI Bridge for AI Power Grid

This bridge connects your local ComfyUI installation to the AI Power Grid, allowing it to work as an image generation worker on the distributed AI network.

## Overview

The ComfyUI Bridge acts as a worker for the AI Power Grid network, receiving image generation jobs, processing them with your local ComfyUI installation, and returning the results to the network.

## Prerequisites

- Python 3.9+
- A running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) instance
- An API key from [AI Power Grid](https://aipowergrid.io/register)

## Installation

1. Clone this repository or download the files
   ```
   git clone --recurse-submodules https://github.com/gonner22/comfy-bride
   ```
3. Create a Python virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install required packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

Edit the `.env` file to set your configuration:

```
# Required: Your API key from AI Power Grid
GRID_API_KEY=your_api_key_here

# Optional: Your worker name (default: ComfyUI-Bridge-Worker)
GRID_WORKER_NAME=your_worker_name

# Optional: ComfyUI URL (default: http://127.0.0.1:8000)
COMFYUI_URL=http://127.0.0.1:8000

# Optional: AI Power Grid API URL (default: https://api.aipowergrid.io/api)
GRID_API_URL=https://api.aipowergrid.io/api

# Optional: Allow NSFW content (default: false)
GRID_NSFW=true

# Optional: Number of concurrent jobs to process (default: 1)
GRID_THREADS=1

# Optional: Maximum image size in pixels (default: 1048576 = 1024x1024)
GRID_MAX_PIXELS=1048576

# Optional: Model to advertise to the grid (default: auto-detected)
GRID_MODEL=stable_diffusion_1.5

# Optional: Workflow file to use (default: api_ready_workflow.json)
WORKFLOW_FILE=api_ready_workflow.json
```

### Model Configuration

The `GRID_MODEL` setting specifies which model your worker advertises to the AI Power Grid. This determines what types of jobs your worker will receive. Common model values include:

- `stable_diffusion_1.5`: Standard SD 1.5 model
- `stable_diffusion_2.1`: SD 2.1 model
- `sdxl`: SDXL 1.0 base model
- `sdxl-turbo`: SDXL Turbo model
- `juggernaut_xl`: Juggernaut XL model
- `playground_v2`: Playground v2 model
- `dreamshaper_8`: Dreamshaper 8 model

The bridge automatically maps these model names to your local checkpoint files. If you don't specify a model, the bridge will try to auto-detect an appropriate model from your ComfyUI installation.

## Running the Bridge

1. Make sure your ComfyUI instance is running
2. Start the bridge:
   ```
   python start_bridge.py
   ```

The bridge will connect to the AI Power Grid, register as a worker, and start processing jobs.

## How It Works

1. The bridge registers with the AI Power Grid as a worker
2. It periodically polls for available jobs
3. When a job is received, it:
   - Converts the job parameters to a ComfyUI workflow
   - Submits the workflow to your local ComfyUI instance
   - Waits for the image generation to complete
   - Returns the generated image to the AI Power Grid
4. The process repeats for new jobs

## Docker: SwarmUI+ComfyUI

SwarmUI is a web interface for AI image and video generation, included in this repository under the `SwarmUI/` folder. It provides an intuitive user interface for generating images and managing workflows.

ComfyUI serves as the integrated backend for SwarmUI, providing a powerful and modular node-based workflow editor. It allows users to create complex image generation pipelines by connecting different nodes that represent operations like loading models, setting prompts, applying image processing, and more. ComfyUI runs as a local web server and provides both a visual interface and API endpoints that both SwarmUI and the bridge use to submit generation jobs.

While SwarmUI is designed to work independently from the bridge, both SwarmUI and the bridge can coexist and complement each other in the same environment by sharing the underlying ComfyUI backend instance.

### Prerequisites for Docker Setup

Before proceeding with the Docker installation, ensure your Linux system meets these requirements:

1. **Docker Engine**
   - Install Docker Engine (not Desktop) following the official guide: https://docs.docker.com/engine/install/
   - Follow the post-installation steps to run Docker as non-root: https://docs.docker.com/engine/install/linux-postinstall/
   - Note: Docker rootless mode is not recommended currently due to unresolved issues

2. **NVIDIA Container Toolkit** 
   - Required for GPU support
   - Install following: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html

3. **Git**
   - Required for cloning repositories
   - Install using your distribution's package manager (e.g., `apt install git`)

### 0. Clone this repository or download the files
   ```
   git clone --recurse-submodules https://github.com/gonner22/comfy-bride
   ```
### 1. Running SwarmUI+ComfyUI with Docker (Standard Version Only)

1. Enter the SwarmUI folder:
   ```bash
   cd SwarmUI
   ./launchtools/launch-standard-docker.sh
   ```
2. Open your browser at [http://0.0.0.0:7801](http://0.0.0.0:7801) (or [http://localhost:7801](http://localhost:7801) if local).
3. Follow the on-screen steps:
   1. **Accept the license agreement.**
   2. Select **Custom Install**.
   3. Choose your preferred theme.
   4. Select **"Just Yourself with LAN access"**.
   5. **IMPORTANT:** **Install ComfyUI as the backend** (this is required for SwarmUI to function).
   6. Download at least the **Stable Diffusion XL 1.0** model, and any others you wish from the list. You can add more models later.
   7. On the final screen, review your selected options and click **"Yes, I'm sure (Install Now)"**.

> **Model storage and symbolic links:**
>
> - Downloaded models are stored in `SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion` (files ending in `.safetensors`).
> - For **comfy-bridge** to easily detect and use these models, it is recommended to create symbolic links in `SwarmUI/Models/Stable-Diffusion` pointing to the models you want to expose.
> - Example: You must be in the `SwarmUI/Models/Stable-Diffusion` directory to run:
>   ```bash
>   ln -s OfficialStableDiffusion/DreamShaperXL_Turbo_v2_1.safetensors DreamShaperXL_Turbo_v2_1.safetensors
>   ```
> - This makes the model visible to both SwarmUI and comfy-bridge. You can repeat this for any other models you wish to use.

### Workflows

The recommended way to load workflows is through the Workflow menu within the application. From there, you can easily:

1. Load your workflow files
2. Set them as the active workflow for image generation
3. Configure any workflow-specific settings

This provides a straightforward interface for managing your workflows without having to manually handle files or configurations.

### Docker Volumes

SwarmUI uses several Docker volumes to persist data and share files between container restarts:

- **swarmdata**: Located at `/SwarmUI/Data`
  - Stores SwarmUI application data, settings, and configurations
  - Persists user preferences and application state

- **swarmbackend**: Located at `/SwarmUI/dlbackend` 
  - Contains the ComfyUI backend installation and dependencies
  - Preserves the ComfyUI environment between container restarts

- **swarmdlnodes**: Located at `/SwarmUI/src/BuiltinExtensions/ComfyUIBackend/DLNodes`
  - Stores custom ComfyUI nodes and extensions
  - Allows adding and managing additional ComfyUI functionality

These volumes ensure your data and configurations persist even when containers are removed and recreated. They are automatically created when first running the Docker container if they don't already exist.

### 2. Docker: Running comfy-bridge

- The setup consists of **two Docker containers**:
  1. ``swarmui``: Contains the SwarmUI interface with ComfyUI backend (already running from previous step)
  2. ``comfy-bridge``: Handles the bridge functionality (instructions detailed below)
- Both containers should be attached to a specific Docker network called `comfy-net`.
- This network allows them to communicate effectively and securely.
- Before running the comfy-bridge container, you must create a `.env` file from the provided template `.env.example`:
  ```bash
  cp .env.example .env
  ```
- Edit the `.env` file and configure the required settings. The container will not start without this file properly configured.
- Make sure the `COMFYUI_URL` in your `.env` points to the SwarmUI/ComfyUI backend (e.g., `http://swarmui:7821` if using Docker service names).
- Other important settings in `.env` include your API key (`GRID_API_KEY`) and worker configuration. See the Configuration section above for details on all available options.

- Example of running both containers on the same network:
  ```bash
  docker network create comfy-net
  # Run SwarmUI (from SwarmUI folder)
  ./launchtools/launch-standard-docker.sh --network comfy-net
  # Run comfy-bridge (from comfy-bridge folder)
  docker run --rm -it \
    --name comfy-bridge \
    --network comfy-net \
    --env-file /path/to/your/.env \
    -v /path/to/your/.env:/app/.env:ro \
    comfy-bridge
  ```

> **Container management tips:**
>
> - To access a running container's shell, use:
>   ```bash
>   docker exec -it swarmui bash -l
>   # or for the bridge container:
>   docker exec -it comfy-bridge bash -l
>   ```
> - To see the status of all containers, use:
>   ```bash
>   docker ps -a
>   ```

---

# Troubleshooting

- **ComfyUI Connection Issues**: Ensure your ComfyUI instance is running and accessible at the URL specified in your `.env` file.
- **API Key Issues**: Verify your GRID_API_KEY is correct and has sufficient permissions.
- **Model Mapping Issues**: The bridge maps AI Power Grid model names to your local ComfyUI models. Check the logs for any mapping errors.
  - If you see "Unknown grid model" warnings, verify that you have the corresponding checkpoint file in your ComfyUI models directory.
  - The bridge attempts to find a matching checkpoint even if names don't match exactly.

# License

This project is licensed under the MIT License - see the LICENSE file for details.

# Acknowledgements

- [AI Power Grid](https://aipowergrid.io/) for the API
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) for the local image generation backend
- [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI) for the modular web UI

---
