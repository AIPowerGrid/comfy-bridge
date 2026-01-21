# Parameter Flow: aipg-art-gallery → comfy-bridge

## Current Flow

### 1. aipg-art-gallery receives request
**Endpoint**: `POST /api/jobs`

**Request Structure** (`CreateJobRequest`):
```json
{
  "modelId": "flux.1-krea-dev",
  "prompt": "A beautiful landscape",
  "negativePrompt": "blurry, low quality",
  "params": {
    "width": 1024,
    "height": 1024,
    "steps": 25,
    "cfgScale": 3.5,
    "sampler": "euler",
    "scheduler": "simple",
    "denoise": 1.0,
    "length": 81,      // for video
    "fps": 24         // for video
  }
}
```

### 2. aipg-art-gallery builds Grid API payload
**Function**: `buildCreateJobPayload()` in `app.go`

**Current Payload Structure** (`CreateJobPayload`):
```go
type CreateJobPayload struct {
    Prompt           string         `json:"prompt"`
    NegativePrompt   string         `json:"negative_prompt,omitempty"`
    Models           []string       `json:"models"`
    Params           map[string]any `json:"params"`  // ← Parameters go here
    // ... other fields
}
```

**Current params map** (lines 819-846):
```go
params := map[string]any{
    "sampler_name":       mappedSampler,
    "scheduler":          scheduler,
    "cfg_scale":          cfgScale,
    "steps":              steps,
    "width":              width,
    "height":             height,
    "seed":               seed,
    "denoising_strength": denoise,  // Note: comfy-bridge expects "denoise"
    "length":             videoLength,
    "video_length":      videoLength,
    "fps":                fps,
}
```

### 3. comfy-bridge receives job
**Function**: `pop_job()` → `process_workflow()`

**Job Structure**:
```python
job = {
    "id": "job-123",
    "model": "flux.1-krea-dev",
    "payload": {
        "prompt": "A beautiful landscape",
        "negative_prompt": "blurry, low quality",
        "params": {  # ← Parameters are nested here
            "steps": 25,
            "cfg_scale": 3.5,
            # ...
        }
    },
    "params": {  # ← Also checked as fallback
        "steps": 25,
        # ...
    }
}
```

**comfy-bridge extraction** (lines 1178-1185):
```python
job_params = job.get("params", {})
payload = job.get("payload", {})

# Checks both locations:
payload_steps = job_params.get("steps") or payload.get("steps")
payload_cfg = job_params.get("cfg_scale") or payload.get("cfg_scale")
# ...
```

## Required Changes

### For aipg-art-gallery

**File**: `server/internal/app/app.go`

**Change**: Update `buildCreateJobPayload()` to include ALL workflow parameters in the `params` map:

```go
params := map[string]any{
    // Existing parameters
    "sampler_name":       mappedSampler,
    "scheduler":          scheduler,
    "cfg_scale":          cfgScale,
    "steps":              steps,
    "width":              width,
    "height":             height,
    "seed":               seed,
    "denoise":            denoise,  // ← Change from "denoising_strength"
    
    // Video parameters
    "length":             videoLength,
    "video_length":      videoLength,
    "fps":                fps,
    "frame_rate":         fps,  // ← Add frame_rate alias
    
    // Additional parameters that workflows might need
    "batch_size":         req.Params.BatchSize,  // ← Add if available
    "filename_prefix":    "",  // ← Optional: let comfy-bridge set default
    "video_format":       req.Params.VideoFormat,  // ← Add if available
    "video_codec":        req.Params.VideoCodec,   // ← Add if available
    
    // Advanced parameters (optional)
    "add_noise":          req.Params.AddNoise,     // ← Add if available
    "start_at_step":      req.Params.StartAtStep,  // ← Add if available
    "end_at_step":        req.Params.EndAtStep,    // ← Add if available
    "shift":              req.Params.Shift,        // ← Add if available
    "guidance":           cfgScale,  // ← Alias for Flux models
}
```

**Also update `JobParamsRequest` struct** (around line 1025) to include new fields:
```go
type JobParamsRequest struct {
    Width      *int     `json:"width,omitempty"`
    Height     *int     `json:"height,omitempty"`
    Steps      *int     `json:"steps,omitempty"`
    CfgScale   *float64 `json:"cfgScale,omitempty"`
    Sampler    *string  `json:"sampler,omitempty"`
    Scheduler  *string  `json:"scheduler,omitempty"`
    Denoise    *float64 `json:"denoise,omitempty"`
    Seed       *string  `json:"seed,omitempty"`
    
    // Video parameters
    Length     *int     `json:"length,omitempty"`
    FPS        *int     `json:"fps,omitempty"`
    FrameRate  *int     `json:"frameRate,omitempty"`
    
    // Additional parameters
    BatchSize      *int     `json:"batchSize,omitempty"`
    VideoFormat    *string  `json:"videoFormat,omitempty"`
    VideoCodec     *string  `json:"videoCodec,omitempty"`
    FilenamePrefix *string  `json:"filenamePrefix,omitempty"`
    
    // Advanced parameters
    AddNoise              *string  `json:"addNoise,omitempty"`  // "enable" or "disable"
    StartAtStep           *int     `json:"startAtStep,omitempty"`
    EndAtStep             *int     `json:"endAtStep,omitempty"`
    ReturnWithLeftoverNoise *string `json:"returnWithLeftoverNoise,omitempty"`
    Shift                 *float64 `json:"shift,omitempty"`
    Guidance              *float64 `json:"guidance,omitempty"`
}
```

### For comfy-bridge

**File**: `comfy_bridge/workflow.py`

**Status**: ✅ Already implemented!

The `process_workflow()` function:
1. ✅ Extracts parameters from `job.get("payload", {})` 
2. ✅ Maps payload keys to placeholder names (snake_case → UPPER_CASE)
3. ✅ Replaces `{{PLACEHOLDER}}` strings in workflows
4. ✅ Falls back to defaults when parameters not provided

**Current parameter mapping** (lines 910-943):
```python
payload_for_placeholders = {}
payload_for_placeholders["SEED"] = seed
payload_for_placeholders["STEPS"] = payload.get("steps")
payload_for_placeholders["CFG"] = payload.get("cfg_scale") or payload.get("cfgScale") or payload.get("cfg")
payload_for_placeholders["SAMPLER"] = payload.get("sampler_name") or payload.get("sampler")
payload_for_placeholders["SCHEDULER"] = payload.get("scheduler")
payload_for_placeholders["DENOISE"] = payload.get("denoise")
payload_for_placeholders["WIDTH"] = payload.get("width")
payload_for_placeholders["HEIGHT"] = payload.get("height")
payload_for_placeholders["BATCH_SIZE"] = payload.get("batch_size")
payload_for_placeholders["LENGTH"] = payload.get("length") or payload.get("video_length")
payload_for_placeholders["PROMPT"] = payload.get("prompt")
payload_for_placeholders["NEGATIVE_PROMPT"] = payload.get("negative_prompt")
payload_for_placeholders["FILENAME_PREFIX"] = payload.get("filename_prefix")
payload_for_placeholders["FPS"] = payload.get("fps")
payload_for_placeholders["FRAME_RATE"] = payload.get("frame_rate")
payload_for_placeholders["VIDEO_FORMAT"] = payload.get("video_format")
payload_for_placeholders["VIDEO_CODEC"] = payload.get("video_codec")
# ... and more
```

**Note**: comfy-bridge checks both:
- `job.get("params", {})` 
- `job.get("payload", {})`

So parameters can be in either location.

## Summary

### What aipg-art-gallery needs to do:
1. ✅ Keep sending parameters in `payload.params` map
2. ✅ Change `"denoising_strength"` → `"denoise"` (comfy-bridge expects "denoise")
3. ✅ Add any missing parameters to `JobParamsRequest` struct
4. ✅ Include all parameters in the `params` map when building payload

### What comfy-bridge does:
1. ✅ Receives parameters from `job.payload.params` or `job.params`
2. ✅ Maps them to placeholder names
3. ✅ Replaces `{{PLACEHOLDER}}` in workflow files
4. ✅ Falls back to defaults when not provided

### Parameter Naming Convention:
- **aipg-art-gallery sends**: `snake_case` (e.g., `cfg_scale`, `sampler_name`)
- **comfy-bridge expects**: `snake_case` in payload, converts to `UPPER_CASE` for placeholders
- **Workflow files use**: `{{UPPER_CASE}}` placeholders (e.g., `{{CFG}}`, `{{SAMPLER}}`)
