import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GRID_API_KEY = os.getenv("GRID_API_KEY", "")
    _GRID_MODELS_RAW = os.getenv("GRID_MODEL", "")
    GRID_MODELS = [m.strip() for m in _GRID_MODELS_RAW.split(",") if m.strip()]
    GRID_WORKER_NAME = os.getenv("GRID_WORKER_NAME", "ComfyUI-Bridge-Worker")
    COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
    # Clean base (no /api) — the new prod nginx serves /v2 directly and the
    # WS worker derives /v1/workers/ws from this. A legacy /api tail is
    # tolerated and stripped where needed.
    GRID_API_URL = os.getenv("GRID_API_URL", "https://api.aipowergrid.io")
    # v2 WebSocket worker protocol (push dispatch + presigned R2 uploads).
    # Off by default until the v2 API is the production default deployment.
    GRID_WS = os.getenv("GRID_WS", "false").lower() == "true"
    NSFW = os.getenv("GRID_NSFW", "false").lower() == "true"
    THREADS = int(os.getenv("GRID_THREADS", "1"))
    MAX_PIXELS = int(os.getenv("GRID_MAX_PIXELS", "20971520"))
    WORKFLOW_DIR = os.getenv("WORKFLOW_DIR", os.path.join(os.getcwd(), "workflows"))
    WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", None)
    GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH = os.getenv("GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH")
    BATCH_SIZE = int(os.getenv("GRID_BATCH_SIZE", "4"))  # Native ComfyUI batch size

    @classmethod
    def validate(cls):
        if not cls.GRID_API_KEY:
            raise RuntimeError("GRID_API_KEY environment variable is required.")
