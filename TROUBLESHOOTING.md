# ComfyUI Bridge Troubleshooting Guide

This guide helps diagnose and fix common issues with the ComfyUI Bridge.

## Quick Diagnostics

Run the configuration checker to quickly identify issues:

```bash
python check_config.py
```

This will check:
- ✅ .env file configuration
- ✅ Workflow files
- ✅ ComfyUI connection
- ✅ API key validity

## Common Issues

### 1. Jobs Stuck in Waiting Queue

**Symptoms:**
- Discord bot shows `waiting: 1, processing: 0, finished: 0`
- Jobs never get processed
- Bridge logs show "No jobs available"

**Causes & Solutions:**

#### A. Bridge Not Advertising Correct Models

The most common cause is model mismatch. Check the bridge startup logs:

```
[INFO] 📢 Advertising 10 models to AI Power Grid:
[INFO]   1. wan2_2_t2v_14b
[INFO]   2. wan2_2_t2v_14b_hq
...
```

If you see `❌ CRITICAL: No models configured!`, fix by:

1. **Use Default Models (Recommended):**
   - Leave `GRID_MODEL=` empty in your `.env` file
   - The bridge will use models from `DEFAULT_WORKFLOW_MAP`

2. **Manual Configuration:**
   - Set `GRID_MODEL=wan2_2_t2v_14b,wan2_2_t2v_14b_hq` in `.env`

#### B. Missing Workflow Files

Check if workflow files exist:

```bash
ls workflows/wan2.2-t2v-a14b.json
ls workflows/wan2.2-t2v-a14b-hq.json
```

If missing, the bridge will show:
```
[WARNING] ⚠️ Missing 1 workflow files:
[WARNING]   wan2_2_t2v_14b -> wan2.2-t2v-a14b.json
```

**Solution:** Ensure all required workflow files are in the `workflows/` directory.

#### C. Bridge Not Running

Make sure the bridge is actually running and polling:

```bash
python start_bridge.py
```

You should see:
```
[INFO] 🔄 Polling for jobs (attempt #1)...
[INFO] Polling for jobs with 10 models: ['wan2_2_t2v_14b', ...]
[INFO] No jobs available (skipped: 0)
```

### 2. ComfyUI Connection Issues

**Symptoms:**
- Bridge crashes on startup
- Error: "Cannot connect to ComfyUI"

**Solutions:**

1. **Check ComfyUI is Running:**
   ```bash
   curl http://localhost:8188/system_stats
   ```

2. **Check URL Configuration:**
   ```bash
   # In .env file
   COMFYUI_URL=http://localhost:8188
   ```

3. **Docker Users:** Use `host.docker.internal` instead of `localhost`

### 3. API Key Issues

**Symptoms:**
- HTTP 401 errors
- "API key is invalid"

**Solutions:**

1. **Get Valid API Key:**
   - Visit https://aipowergrid.io/register
   - Generate an API key
   - Set in `.env`: `GRID_API_KEY=your_actual_key_here`

2. **Check API Key Format:**
   - Should be a long alphanumeric string
   - Not "your_api_key_here" (the example value)

### 4. Model Not Found Errors

**Symptoms:**
- Bridge picks up jobs but fails with "model not found"
- ComfyUI errors about missing checkpoints

**Solutions:**

1. **Install Required Models:**
   - For video generation, ensure you have the required model files in ComfyUI
   - Check ComfyUI logs for missing model files

2. **Update Workflow Files:**
   - Ensure workflow files reference the correct model names
   - Check node configurations match your installed models

## Enhanced Logging

For detailed debugging, the bridge provides enhanced logging:

```
[INFO] 🚀 ComfyUI Bridge starting...
[INFO] Connecting to ComfyUI at: http://localhost:8188
[INFO] Connecting to AI Power Grid at: https://api.aipowergrid.io/api
[INFO] Worker name: MyComfyWorker.APIG_Wallet
[INFO] 📋 Built workflow map with 10 models:
[INFO]   wan2_2_t2v_14b -> wan2.2-t2v-a14b.json
[INFO]   wan2_2_t2v_14b_hq -> wan2.2-t2v-a14b-hq.json
...
[INFO] 📢 Advertising 10 models to AI Power Grid:
[INFO]   1. wan2_2_t2v_14b
[INFO]   2. wan2_2_t2v_14b_hq
...
[INFO] 🔄 Polling for jobs (attempt #1)...
[INFO] Polling for jobs with 10 models: ['wan2_2_t2v_14b', ...]
[INFO] ✓ Got job abc123 for model wan2_2_t2v_14b
[INFO] 🎯 Processing job abc123 for model wan2_2_t2v_14b
```

## Still Need Help?

1. **Run Full Diagnostics:**
   ```bash
   python check_config.py
   ```

2. **Check Log Files:**
   ```bash
   tail -f bridge.log
   ```

3. **Provide Debug Info:**
   When asking for help, include:
   - Output of `python check_config.py`
   - Bridge startup logs (first 50 lines)
   - Any error messages
   - Your `.env` configuration (hide your API key!)

## Video Generation Specific Issues

### Models Not Matching

**Discord Bot Model vs Bridge Model:**
- Discord bot logs: `Model: wan2_2_t2v_14b`
- Bridge should advertise: `wan2_2_t2v_14b`

Make sure the model names match exactly (case-sensitive).

### Workflow Configuration

Video workflows need special nodes:
- Video generation nodes (specific to your ComfyUI setup)
- Proper video output formats
- Correct video parameters (fps, length, etc.)

Check that your workflow files in `workflows/` directory are compatible with video generation.
