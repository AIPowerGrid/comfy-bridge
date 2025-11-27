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
2. Create a Python virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install required packages:
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

## Troubleshooting

- **ComfyUI Connection Issues**: Ensure your ComfyUI instance is running and accessible at the URL specified in your `.env` file.
- **API Key Issues**: Verify your GRID_API_KEY is correct and has sufficient permissions.
- **Model Mapping Issues**: The bridge maps AI Power Grid model names to your local ComfyUI models. Check the logs for any mapping errors.
  - If you see "Unknown grid model" warnings, verify that you have the corresponding checkpoint file in your ComfyUI models directory.
  - The bridge attempts to find a matching checkpoint even if names don't match exactly.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [AI Power Grid](https://aipowergrid.io/) for the API
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) for the local image generation backend 