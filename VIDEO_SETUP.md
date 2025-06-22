# Video Generation Setup Guide

This guide explains how to configure the ComfyUI Bridge to work with video generation models like Wan 2.1, supporting both Text-to-Video (T2V) and Image-to-Video (I2V) workflows.

## Prerequisites

1. ComfyUI installed with video generation capabilities
2. Wan 2.1 model files:
   - `Wan2.1_T2V_14B_FusionX-Q8_0.gguf` (T2V UNet model)
   - `Wan2.1_I2V_14B_FusionX-Q8_0.gguf` (I2V UNet model)
   - `umt5-xxl-encoder-Q8_0.gguf` (CLIP encoder) 
   - `Wan2_1_VAE_bf16.safetensors` (VAE)
   - `clip_vision_h.safetensors` (CLIP Vision for I2V)
3. Video Combine nodes (VHS extension for ComfyUI)

## Configuration

Create a `.env` file with the following settings:

```env
# Required: Your API key from AI Power Grid
GRID_API_KEY=your_api_key_here

# Worker name for video generation
GRID_WORKER_NAME=Wan-2.1-Video-Worker

# ComfyUI URL (adjust port if needed)
COMFYUI_URL=http://127.0.0.1:8188

# Model to advertise to the grid (choose one)
GRID_MODEL=wan_2.1        # For Text-to-Video
# GRID_MODEL=wan_2.1_i2v  # For Image-to-Video

# Video workflow file (choose one)
WORKFLOW_FILE=wan_2.1_video.json    # For Text-to-Video
# WORKFLOW_FILE=wan_2.1_i2v.json    # For Image-to-Video

# Allow NSFW content if needed
GRID_NSFW=true

# Other optional settings
GRID_THREADS=1
GRID_MAX_PIXELS=1048576
```

## Video Parameters

The bridge now supports these video-specific parameters:

- `video_frames`: Number of frames to generate (default: 81)
- `frame_rate`: Output video frame rate (default: 16)  
- `video_length`: Video length in seconds (default: 5.0)
- `width`: Video width (default: 1024)
- `height`: Video height (default: 576)

### I2V-Specific Parameters

- `input_image`: Base64 encoded input image for I2V workflows
- `input_image_filename`: Filename for the input image (default: "input_image.png")

## Workflow File

The bridge includes two workflow templates:

### Text-to-Video (`wan_2.1_video.json`)
1. Uses `UnetLoaderGGUF` and `CLIPLoaderGGUF` for model loading
2. Generates video latents with `EmptyHunyuanLatentVideo`
3. Outputs MP4 videos with `VHS_VideoCombine`
4. Supports dynamic parameter injection

### Image-to-Video (`wan_2.1_i2v.json`)
1. Uses `UnetLoaderGGUF` and `CLIPLoaderGGUF` for model loading
2. Loads input image with `LoadImage`
3. Processes image with `CLIPVisionLoader` and `CLIPVisionEncode`
4. Generates video with `WanImageToVideo`
5. Outputs MP4 videos with `VHS_VideoCombine`
6. Supports dynamic parameter injection including input image handling

## Running Video Generation

1. Make sure your ComfyUI instance is running with the Wan 2.1 models loaded

2. Start the bridge for Text-to-Video:
   ```bash
   python start_bridge.py --workflow wan_2.1_video.json --grid-model wan_2.1
   ```

3. Or start the bridge for Image-to-Video:
   ```bash
   python start_bridge.py --workflow wan_2.1_i2v.json --grid-model wan_2.1_i2v
   ```

4. The bridge will advertise as a video worker and process video generation jobs

## Supported Video Models

The model mapper now recognizes these video models:

- `wan_2.1` / `wan2.1`: Maps to Wan 2.1 T2V model
- `wan_2.1_i2v` / `wan2.1_i2v`: Maps to Wan 2.1 I2V model
- `stable_video_diffusion` / `svd`: Maps to SVD models
- `animatediff`: Maps to AnimateDiff models

## Troubleshooting

- **Model not found**: Ensure your model files are in the correct ComfyUI directories
- **Video output issues**: Check that the VHS extension is installed in ComfyUI
- **Memory issues**: Video generation requires significantly more VRAM than images
- **Slow generation**: Video generation takes much longer than images (several minutes per video)

## Output Format

Generated videos are returned as MP4 files with H.264 encoding. The bridge automatically handles the conversion from ComfyUI's output format to the format expected by the AI Power Grid. 