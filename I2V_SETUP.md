# Image-to-Video (I2V) Setup Guide

This guide focuses on setting up the ComfyUI Bridge specifically for Image-to-Video generation with Wan 2.1 I2V.

## Quick Setup for I2V

### 1. Prerequisites
- ComfyUI with Wan 2.1 I2V model files:
  - `Wan2.1_I2V_14B_FusionX-Q8_0.gguf` (I2V UNet)
  - `umt5-xxl-encoder-Q8_0.gguf` (CLIP encoder)
  - `Wan2_1_VAE_bf16.safetensors` (VAE)
  - `clip_vision_h.safetensors` (CLIP Vision)
- VHS extension for video output

### 2. Configuration (.env file)
```env
GRID_API_KEY=your_api_key_here
GRID_WORKER_NAME=Wan-2.1-I2V-Worker
COMFYUI_URL=http://127.0.0.1:8188
GRID_MODEL=wan_2.1_i2v
WORKFLOW_FILE=wan_2.1_i2v.json
GRID_NSFW=true
```

### 3. Start I2V Bridge
```bash
python start_bridge.py --workflow wan_2.1_i2v.json --grid-model wan_2.1_i2v
```

## I2V-Specific Features

### Input Image Handling
- The bridge automatically saves base64 input images to ComfyUI's input directory
- Images are referenced by filename in the workflow
- Supports common image formats (PNG, JPG, WebP)

### Workflow Structure
The I2V workflow (`wan_2.1_i2v.json`) includes:
1. **LoadImage** - Loads the input image
2. **CLIPVisionLoader/CLIPVisionEncode** - Processes image for conditioning
3. **WanImageToVideo** - Core I2V generation node
4. **VHS_VideoCombine** - Creates MP4 output

### Parameter Injection
All standard video parameters are supported:
- `prompt`: Text description of the desired motion/changes
- `negative_prompt`: What to avoid in the video
- `video_frames`: Number of frames (default: 81)
- `frame_rate`: Output FPS (default: 16)
- `width/height`: Video dimensions (default: 1024x576)
- `input_image`: Base64 encoded source image
- `input_image_filename`: Name for the saved image file

## Example Usage

When the bridge receives an I2V job, it will:
1. Save the input image to ComfyUI's input directory
2. Inject all parameters into the workflow
3. Generate a video based on the input image and prompt
4. Return the MP4 video to the AI Power Grid

The I2V workflow is perfect for creating dynamic videos from static images, such as:
- Adding motion to portraits
- Animating landscapes
- Creating cinemagraphs
- Bringing artwork to life

## Troubleshooting I2V

- **Image not found**: Ensure the input image is properly base64 encoded
- **CLIP Vision errors**: Verify `clip_vision_h.safetensors` is in your models directory
- **Memory issues**: I2V requires more VRAM than T2V due to image processing
- **Slow generation**: I2V typically takes longer than T2V due to additional conditioning 