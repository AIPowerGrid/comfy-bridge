import os
from dotenv import load_dotenv  # type: ignore  # dotenv installed via requirements.txt in Docker

load_dotenv()


class Settings:
    GRID_API_KEY = os.getenv("GRID_API_KEY", "")
    _WORKFLOW_MODELS_RAW = os.getenv("WORKFLOW_FILE", "")
    GRID_MODELS = [m.strip() for m in _WORKFLOW_MODELS_RAW.split(",") if m.strip()]
    GRID_WORKER_NAME = os.getenv("GRID_WORKER_NAME", "ComfyUI-Bridge-Worker")
    COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8000")
    GRID_API_URL = os.getenv("GRID_API_URL", "https://api.aipowergrid.io/api")
    NSFW = os.getenv("GRID_NSFW", "false").lower() == "true"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    THREADS = int(os.getenv("GRID_THREADS", "1"))
    MAX_PIXELS = int(os.getenv("GRID_MAX_PIXELS", "20971520"))
    # Default workflows path relative to this package: /app/comfy-bridge/workflows
    WORKFLOW_DIR = os.getenv(
        "WORKFLOW_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "workflows"),
    )
    WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", None)
    COMFYUI_OUTPUT_DIR = os.getenv("COMFYUI_OUTPUT_DIR", r"C:\dev\ComfyUI\output")
    GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH = os.getenv("GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH")
    # ModelVault on-chain validation (Base Sepolia)
    MODELVAULT_ENABLED = os.getenv("MODELVAULT_ENABLED", "true").lower() == "true"
    MODELVAULT_RPC_URL = os.getenv("MODELVAULT_RPC_URL", "https://sepolia.base.org")
    MODELVAULT_CONTRACT = os.getenv("MODELVAULT_CONTRACT", "0xe660455D4A83bbbbcfDCF4219ad82447a831c8A1")

    @classmethod
    def validate(cls):
        if not cls.GRID_API_KEY:
            raise RuntimeError("GRID_API_KEY environment variable is required.")
