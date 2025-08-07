from typing import Dict, Any
from .utils import generate_seed
from .model_mapper import map_model_name


def build_workflow(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = job.get("payload", {})
    model_ckpt = map_model_name(job.get("model", "")) or job.get("model", "")
    seed = generate_seed(payload.get("seed"))

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": payload.get("steps", 30),
                "cfg": payload.get("cfg_scale", 7.0),
                "model": ["4", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": model_ckpt},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": payload.get("prompt", ""), "clip": ["4", 1]},
        },
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": payload.get("width", 512),
                "height": payload.get("height", 512),
                "batch_size": 1,
            },
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": f"horde_{job.get('id','')}",
                "images": ["7", 0],
            },
        },
    }
