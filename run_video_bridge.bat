@echo off
echo Setting up environment for video generation with wan2.2_t2v...

REM AI Power Grid API configuration
REM Replace with your actual API key
set GRID_API_KEY=CADWOATvdPmE7npsuLv1bQ
set GRID_API_URL=https://api.aipowergrid.io/api
set GRID_WORKER_NAME=ameli0x.AdD3DPyBpd2pgoAQD59EwZLniVwmC6Gfj9

REM ComfyUI configuration - this should be local
set COMFYUI_URL=http://127.0.0.1:8000

REM Worker capabilities
set GRID_NSFW=false
set GRID_THREADS=1
set GRID_MAX_PIXELS=20971520

REM Workflow configuration
set WORKFLOW_DIR=workflows
set WORKFLOW_FILE=wan2_2_t2v_14b.json
set GRID_MODEL=wan2.2-t2v-a14b

REM Reference data
set GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH=grid-image-model-reference

echo Starting bridge with video support...
python -m comfy_bridge.cli
