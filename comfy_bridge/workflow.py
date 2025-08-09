from typing import Dict, Any
from .utils import generate_seed
from .model_mapper import map_model_name


def build_workflow(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = job.get("payload", {})
    model_name = job.get("model", "")
    model_ckpt = map_model_name(model_name) or model_name
    seed = generate_seed(payload.get("seed"))
    
    # Check if this is a Flux model
    if "flux" in model_name.lower() or "flux" in model_ckpt.lower():
        return build_flux_workflow(job, payload, model_ckpt, seed)
    else:
        return build_sd_workflow(job, payload, model_ckpt, seed)


def build_flux_workflow(job: Dict[str, Any], payload: Dict[str, Any], model_ckpt: str, seed: int) -> Dict[str, Any]:
    """Build workflow for Flux models using UNETLoader"""
    return {
        "27": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": payload.get("width", 1024),
                "height": payload.get("height", 1024),
                "batch_size": 1,
            },
        },
        "31": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": payload.get("ddim_steps", 20),
                "cfg": payload.get("cfg_scale", 1.0),
                "sampler_name": payload.get("sampler_name", "euler").replace("k_", ""),
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["38", 0],
                "positive": ["45", 0],
                "negative": ["42", 0],
                "latent_image": ["27", 0],
            },
        },
        "38": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": model_ckpt,
                "weight_dtype": "default",
            },
        },
        "39": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "40": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5xxl_fp16.safetensors",
                "type": "flux",
                "device": "default",
            },
        },
        "42": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["45", 0]},
        },
        "45": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": payload.get("prompt", ""),
                "clip": ["40", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["31", 0],
                "vae": ["39", 0],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": f"horde_{job.get('id','')}",
                "images": ["8", 0],
            },
        },
    }


def build_sd_workflow(job: Dict[str, Any], payload: Dict[str, Any], model_ckpt: str, seed: int) -> Dict[str, Any]:
    """Build workflow for Stable Diffusion models using CheckpointLoaderSimple"""
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
