# Workflow Files

Workflow files must be exported from ComfyUI with actual model file names, not placeholders.

## Exporting Workflows from ComfyUI

1. Open ComfyUI in your browser
2. Load the model you want to create a workflow for
3. Build your workflow using the actual model files
4. Click "Save" or use Ctrl+S to save the workflow
5. Export the workflow JSON (right-click → Save As, or use the API)
6. Place the exported JSON file in the `workflows/` directory

## Important: Use Actual Model File Names

**DO NOT** use placeholder names like:
- ❌ `checkpoint_name.safetensors`
- ❌ `model.safetensors`
- ❌ `checkpoint.safetensors`

**DO** use actual model file names that exist in ComfyUI:
- ✅ `flux1-dev.safetensors`
- ✅ `wan2.2_ti2v_5B_fp16.safetensors`
- ✅ `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

## Workflow File Naming

Workflow files should be named to match the Grid model name:
- Model: `FLUX.1-dev` → Workflow: `FLUX.1-dev.json` or `flux1.dev.json`
- Model: `wan2.2-t2v-a14b` → Workflow: `wan2.2-t2v-a14b.json`

## Fixing Existing Workflows

If a workflow has placeholder model names, you must:
1. Open it in ComfyUI
2. Load the actual model files
3. Re-export the workflow with real model names

