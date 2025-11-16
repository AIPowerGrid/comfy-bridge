# Workflow Files

Workflows must be exported from ComfyUI with actual model file names, not placeholders.

## Exporting from ComfyUI

1. Open ComfyUI and load the model
2. Build workflow with actual model files
3. Export workflow JSON
4. Place in `workflows/` directory

## Model File Names

Use actual model file names:
- `flux1-dev.safetensors`
- `wan2.2_ti2v_5B_fp16.safetensors`

Do not use placeholders:
- `checkpoint_name.safetensors`
- `model.safetensors`

## File Naming

Match Grid model name:
- `FLUX.1-dev` → `FLUX.1-dev.json` or `flux1.dev.json`
- `wan2.2-t2v-a14b` → `wan2.2-t2v-a14b.json`

