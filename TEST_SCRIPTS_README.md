# Test Scripts for Image/Video Generation API

This directory contains test scripts to verify that image and video generation works correctly with the AI PowerGrid API.

## Files

### Image Generation
- `test_image_generation.sh` - Comprehensive bash script with multiple test cases
- `test_image_generation.ps1` - PowerShell version for Windows
- `test_simple_curl.sh` - Simple single curl command
- `test_curl_examples.sh` - Quick curl examples
- `test_image_generation.json` - JSON examples for reference

### Video Generation (Image-to-Video)
- `test_ltx2_i2v.ps1` - PowerShell script for ltx2_i2v (image-to-video) jobs
- `test_ltx2_i2v.sh` - Bash script for ltx2_i2v jobs
- `test_ltx2_i2v_curl.sh` - Simple curl examples for ltx2_i2v
- `test_i2v.py` - Python tests for i2v workflow routing

## Quick Start

### Bash (Linux/Mac/Git Bash)

```bash
# Set environment variables
export API_BASE_URL=http://localhost:8080
export API_KEY=your-api-key-here
export MODEL_ID=flux.1-krea-dev

# Run the test script
chmod +x test_image_generation.sh
./test_image_generation.sh
```

### PowerShell (Windows)

```powershell
# Set environment variables
$env:API_BASE_URL = "http://localhost:8080"
$env:API_KEY = "your-api-key-here"
$env:MODEL_ID = "flux.1-krea-dev"

# Run the test script
.\test_image_generation.ps1
```

### Simple curl command

```bash
# Edit test_simple_curl.sh and replace YOUR_API_KEY
chmod +x test_simple_curl.sh
./test_simple_curl.sh
```

## Test Cases

All tests use the `flux.1-krea-dev` model for image generation.

### Test 1: Basic Image Generation
Minimal parameters - tests default fallback behavior:
- `width`, `height`, `steps`, `cfgScale` only
- Other parameters should use workflow defaults

### Test 2: Full Parameters
All workflow parameters provided:
- `width`, `height`, `steps`, `cfgScale`
- `sampler`, `scheduler`, `denoise`, `seed`
- Tests that all placeholders are replaced correctly

### Test 3: Job Status Check
Verifies that job status can be retrieved after submission

## Expected Parameters

The API expects parameters in the `params` object:

```json
{
  "modelId": "flux.1-krea-dev",
  "prompt": "Your prompt here",
  "negativePrompt": "Optional negative prompt",
  "apiKey": "your-api-key",
  "params": {
    "width": 1024,
    "height": 1024,
    "steps": 25,
    "cfgScale": 3.5,
    "sampler": "euler",
    "scheduler": "simple",
    "denoise": 1.0,
    "seed": "12345"
  }
}
```

## Parameter Mapping

Parameters sent from aipg-art-gallery are mapped to workflow placeholders:

| API Parameter | Workflow Placeholder | Default Value |
|--------------|---------------------|---------------|
| `steps` | `{{STEPS}}` | 20 |
| `cfgScale` | `{{CFG}}` | 3.5 |
| `sampler` | `{{SAMPLER}}` | "euler" |
| `scheduler` | `{{SCHEDULER}}` | "simple" |
| `denoise` | `{{DENOISE}}` | 1.0 |
| `width` | `{{WIDTH}}` | 1024 |
| `height` | `{{HEIGHT}}` | 1024 |
| `seed` | `{{SEED}}` | Generated |

## Checking Job Status

After submitting a job, check its status:

```bash
curl -X GET http://localhost:8080/api/jobs/{jobId}
```

## Troubleshooting

### Error: "invalid payload"
- Check that `modelId`, `prompt`, and `apiKey` are provided
- Verify JSON syntax is correct

### Error: "unknown model"
- Verify the `modelId` matches a model in the catalog
- Check model name case sensitivity

### Parameters not working
- Verify parameters are in the `params` object
- Check that parameter names match expected format (camelCase)
- Ensure comfy-bridge is receiving parameters from `job.payload.params`

### Default values not applied
- Check comfy-bridge logs for placeholder replacement
- Verify workflow files have `{{PLACEHOLDER}}` syntax
- Ensure `_replace_placeholders()` function is being called

## Example Responses

### Success Response
```json
{
  "jobId": "abc123-def456",
  "status": "queued"
}
```

### Job Status Response
```json
{
  "jobId": "abc123-def456",
  "status": "completed",
  "generations": [
    {
      "id": "gen-123",
      "url": "https://...",
      "seed": "12345"
    }
  ]
}
```

---

## LTX2 Image-to-Video (ltx2_i2v)

The `ltx2_i2v` model converts a single image into a short video (~5 seconds at 25fps).

### Quick Start

#### PowerShell (Windows)
```powershell
# Set your API key
$env:API_KEY = "your-api-key-here"

# Run the test with an image
.\test_ltx2_i2v.ps1 -ImagePath "path\to\your\image.png" -Prompt "A gentle breeze animates the scene"
```

#### Bash (Linux/Mac)
```bash
# Set your API key
export API_KEY="your-api-key-here"

# Run the test with an image
chmod +x test_ltx2_i2v.sh
./test_ltx2_i2v.sh ./your_image.png "A gentle breeze animates the scene"
```

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `modelId` | Must be `"ltx2_i2v"` |
| `sourceImage` | Base64-encoded image (no data: prefix) |
| `sourceProcessing` | Must be `"img2video"` |
| `mediaType` | Must be `"video"` |
| `prompt` | Text description of the video motion |

### Video Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `width` | Video width | 1280 | 512-1920 |
| `height` | Video height | 720 | 512-1080 |
| `steps` | Inference steps | 20 | 10-50 |
| `cfgScale` | Guidance scale | 4.0 | 1.0-10.0 |
| `length` | Number of frames | 121 | 25-200 |
| `fps` | Frames per second | 25 | 15-30 |

### Example API Request

```json
{
  "modelId": "ltx2_i2v",
  "prompt": "The woman smiles warmly and waves hello",
  "negativePrompt": "blurry, low quality, still frame, watermark",
  "apiKey": "your-api-key",
  "sourceImage": "BASE64_IMAGE_DATA_WITHOUT_PREFIX",
  "sourceProcessing": "img2video",
  "mediaType": "video",
  "params": {
    "width": 1280,
    "height": 720,
    "steps": 20,
    "cfgScale": 4.0,
    "length": 121,
    "fps": 25
  }
}
```

### Video Response

```json
{
  "jobId": "abc123",
  "status": "completed",
  "generations": [{
    "id": "gen123",
    "kind": "video",
    "mimeType": "video/mp4",
    "url": "https://images.aipg.art/gen123.mp4",
    "seed": "12345",
    "workerName": "my-worker"
  }]
}
```

### Processing Flow

1. **Submit Job**: Client sends job with base64 image to `/api/jobs`
2. **Queue**: Job enters the Grid API queue for `ltx2_i2v` model
3. **Worker Pop**: comfy-bridge worker polls for jobs with `ltx2_i2v` model
4. **Download Image**: Worker downloads source_image to ComfyUI input folder
5. **Process**: Worker runs `ltx2_i2v.json` workflow in ComfyUI
6. **Upload**: Worker uploads generated video to R2 storage
7. **Submit Result**: Worker submits result with video URL to Grid API
8. **Complete**: Client retrieves video URL from job status

### Notes

- Video generation typically takes 2-5 minutes depending on GPU
- The worker must be running and advertising `ltx2_i2v` model
- Videos are stored in R2 and accessible via CDN URL
- The `sourceImage` must be raw base64 (no `data:image/...` prefix)
