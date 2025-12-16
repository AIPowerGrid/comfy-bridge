import json
import os
import copy
import httpx  # type: ignore  # httpx installed via requirements.txt in Docker
import uuid
import logging
from typing import Dict, Any, Optional, Tuple, List
from .utils import generate_seed
from .model_mapper import get_workflow_file
from .config import Settings
from .wan_assets import ensure_wan_symlinks

logger = logging.getLogger(__name__)


def detect_workflow_model_type(workflow: Dict[str, Any]) -> str:
    """Detect the model type (flux, wanvideo, sdxl, etc.) from workflow nodes"""
    # Handle ComfyUI native format (has "nodes" array)
    if isinstance(workflow, dict) and "nodes" in workflow:
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            
            class_type = node.get("type", "")
            
            # WanVideo workflows use WanVideo-specific or Hunyuan latent nodes
            if class_type in [
                "WanVideoModelLoader",
                "WanVideoVAELoader",
                "WanVideoSampler",
                "WanVideoTextEmbedBridge",
                "WanVideoEmptyEmbeds",
                "WanVideoDecode",
                "EmptyHunyuanLatentVideo",
                "Wan22ImageToVideoLatent",
            ]:
                return "wanvideo"
            
            # Flux workflows use DualCLIPLoader + UNETLoader + VAELoader
            if class_type == "DualCLIPLoader":
                return "flux"
            
            # SDXL workflows use CheckpointLoaderSimple
            if class_type == "CheckpointLoaderSimple":
                return "sdxl"
    
    # Handle simple format (direct node objects)
    else:
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get("class_type", "")
            
            # WanVideo workflows use WanVideo-specific or Hunyuan latent nodes
            if class_type in [
                "WanVideoModelLoader",
                "WanVideoVAELoader",
                "WanVideoSampler",
                "WanVideoTextEmbedBridge",
                "WanVideoEmptyEmbeds",
                "WanVideoDecode",
                "EmptyHunyuanLatentVideo",
                "Wan22ImageToVideoLatent",
            ]:
                return "wanvideo"
            
            # Flux workflows use DualCLIPLoader + UNETLoader + VAELoader
            if class_type == "DualCLIPLoader":
                return "flux"
            
            # SDXL workflows use CheckpointLoaderSimple
            if class_type == "CheckpointLoaderSimple":
                return "sdxl"
    
    # Default to unknown if we can't detect
    return "unknown"


def is_model_compatible(model_name: str, model_type: str) -> bool:
    """Check if a model filename is compatible with the workflow model type"""
    model_lower = model_name.lower()
    
    if model_type == "flux":
        # Flux models: flux1CompactCLIP, umt5, flux1-krea-dev, ae.safetensors
        return any(keyword in model_lower for keyword in [
            "flux", "umt5", "clip_l", "t5xxl", "ae.safetensors"
        ])
    elif model_type == "wanvideo":
        # WanVideo models: wan2.2, wan_2.1
        return any(keyword in model_lower for keyword in [
            "wan2", "wan_2", "wan2.2"
        ])
    elif model_type == "sdxl":
        # SDXL models
        return "sdxl" in model_lower or "xl" in model_lower
    
    return False


def _force_video_processing(job: Dict[str, Any], model_type: str) -> None:
    """Video models cannot run through img2img flow – force img2vid semantics."""
    if model_type != "wanvideo":
        return

    current_processing = job.get("source_processing")
    if current_processing != "img2vid":
        job["source_processing"] = "img2vid"
        logger.info(
            "Overriding source_processing for WanVideo job %s: %s -> img2vid",
            job.get("id", "unknown"),
            current_processing or "unset",
        )


async def validate_and_fix_model_filenames(
    workflow: Dict[str, Any], 
    available_models: Dict[str, Any],
    job_model_name: Optional[str] = None
) -> Dict[str, Any]:
    """Validate and fix model filenames in workflow to match available models.
    
    Uses job_model_name to select the best matching checkpoint when available.
    Only replaces models with compatible model types (e.g., Flux with Flux, WanVideo with WanVideo).
    Fails if no compatible models are available.
    
    Handles both ComfyUI native format (nodes array) and simple format (dict of nodes).
    """
    fixed_workflow = copy.deepcopy(workflow)
    fixes_applied = []
    model_type = detect_workflow_model_type(workflow)
    
    logger.info(f"Detected workflow model type: {model_type}, job model: {job_model_name}")
    
    if model_type == "unknown":
        logger.warning("Could not detect workflow model type - proceeding with validation anyway")
    if model_type == "wanvideo":
        ensure_wan_symlinks()
    
    # Helper to fetch loader options safely
    def _get_loader_options(loader_key: str, sub_key: Optional[str] = None) -> List[str]:
        raw = available_models.get(loader_key)
        if not raw:
            logger.warning(f"No loader data returned for {loader_key} - skipping strict validation for this loader")
            return []
        if sub_key and isinstance(raw, dict):
            return raw.get(sub_key, []) or []
        if isinstance(raw, list):
            return raw
        return []

    # Handle ComfyUI native format (has "nodes" array)
    if isinstance(workflow, dict) and "nodes" in workflow:
        nodes = fixed_workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            
            node_id = node.get("id")
            class_type = node.get("type", "")
            
            # Skip validation for WanVideo models in native format - they're handled differently
            if model_type == "wanvideo":
                continue
            
            # Handle Flux models in native format
            if class_type == "DualCLIPLoader" and model_type == "flux":
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) >= 2:
                    # widgets_values: [clip_name1, clip_name2, ...]
                    clip1_options = _get_loader_options("DualCLIPLoader", "clip_name1")
                    clip2_options = _get_loader_options("DualCLIPLoader", "clip_name2")
                    
                    if model_type == "flux":
                        clip1_options = [m for m in clip1_options if is_model_compatible(m, "flux")]
                        clip2_options = [m for m in clip2_options if is_model_compatible(m, "flux")]
                    
                    if not clip1_options:
                        # If workflow requires DualCLIPLoader but no compatible models are available, fail
                        current_clip1 = widgets[0] if len(widgets) > 0 else "unknown"
                        all_dual_clip = available_models.get("DualCLIPLoader", {})
                        all_clip1 = all_dual_clip.get("clip_name1", []) if isinstance(all_dual_clip, dict) else []
                        raise ValueError(
                            f"Required DualCLIPLoader clip_name1 '{current_clip1}' is not available. "
                            f"No compatible clip_name1 models found in ComfyUI for {model_type} workflow. "
                            f"Available clip_name1 models: {all_clip1}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif widgets[0] not in clip1_options:
                        old_clip1 = widgets[0]
                        widgets[0] = clip1_options[0]
                        fixes_applied.append(f"Node {node_id} clip_name1: {old_clip1} -> {widgets[0]}")
                    
                    if len(widgets) >= 2:
                        if not clip2_options:
                            # If workflow requires DualCLIPLoader but no compatible models are available, fail
                            current_clip2 = widgets[1] if len(widgets) > 1 else "unknown"
                            all_dual_clip = available_models.get("DualCLIPLoader", {})
                            all_clip2 = all_dual_clip.get("clip_name2", []) if isinstance(all_dual_clip, dict) else []
                            raise ValueError(
                                f"Required DualCLIPLoader clip_name2 '{current_clip2}' is not available. "
                                f"No compatible clip_name2 models found in ComfyUI for {model_type} workflow. "
                                f"Available clip_name2 models: {all_clip2}. "
                                f"Please ensure required model files are installed in the ComfyUI models directory."
                            )
                        elif widgets[1] not in clip2_options:
                            old_clip2 = widgets[1]
                            widgets[1] = clip2_options[0]
                            fixes_applied.append(f"Node {node_id} clip_name2: {old_clip2} -> {widgets[1]}")
                    
                    node["widgets_values"] = widgets
            
            elif class_type == "UNETLoader" and model_type == "flux":
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) >= 1:
                    unet_options = _get_loader_options("UNETLoader")
                    if model_type == "flux":
                        unet_options = [m for m in unet_options if is_model_compatible(m, "flux")]
                    
                    if not unet_options:
                        # If workflow requires UNETLoader but no compatible models are available, fail
                        current_unet = widgets[0] if len(widgets) > 0 else "unknown"
                        all_unet_models = available_models.get("UNETLoader", [])
                        raise ValueError(
                            f"Required UNETLoader model '{current_unet}' is not available. "
                            f"No compatible UNETLoader models found in ComfyUI for {model_type} workflow. "
                            f"Available UNETLoader models: {all_unet_models}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif widgets[0] not in unet_options:
                        old_unet = widgets[0]
                        widgets[0] = unet_options[0]
                        fixes_applied.append(f"Node {node_id} unet_name: {old_unet} -> {widgets[0]}")
                        node["widgets_values"] = widgets
            
            elif class_type == "VAELoader" and model_type == "flux":
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) >= 1:
                    vae_options = _get_loader_options("VAELoader")
                    if model_type == "flux":
                        vae_options = [m for m in vae_options if is_model_compatible(m, "flux")]
                    
                    if not vae_options:
                        # If workflow requires VAELoader but no compatible models are available, fail
                        current_vae = widgets[0] if len(widgets) > 0 else "unknown"
                        all_vae_models = available_models.get("VAELoader", [])
                        raise ValueError(
                            f"Required VAELoader model '{current_vae}' is not available. "
                            f"No compatible VAELoader models found in ComfyUI for {model_type} workflow. "
                            f"Available VAELoader models: {all_vae_models}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif widgets[0] not in vae_options:
                        old_vae = widgets[0]
                        widgets[0] = vae_options[0]
                        fixes_applied.append(f"Node {node_id} vae_name: {old_vae} -> {widgets[0]}")
                        node["widgets_values"] = widgets
    
    # Handle simple format (direct node objects)
    else:
        for node_id, node_data in fixed_workflow.items():
            if not isinstance(node_data, dict):
                continue
                
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
        
            # Fix DualCLIPLoader (Flux models)
            if class_type == "DualCLIPLoader":
                if model_type != "flux":
                    logger.warning(f"Node {node_id}: DualCLIPLoader found but workflow type is {model_type} - may be incompatible")
                
                dual_clip_models = available_models.get("DualCLIPLoader") or {}
                clip1_options = dual_clip_models.get("clip_name1", []) if isinstance(dual_clip_models, dict) else []
                clip2_options = dual_clip_models.get("clip_name2", []) if isinstance(dual_clip_models, dict) else []
                
                # Filter to compatible models only
                if model_type == "flux":
                    clip1_options = [m for m in clip1_options if is_model_compatible(m, "flux")]
                    clip2_options = [m for m in clip2_options if is_model_compatible(m, "flux")]
                
                # Check clip_name1 - must check if input exists FIRST, then validate options
                if "clip_name1" in inputs:
                    current_clip1 = inputs.get("clip_name1")
                    if not clip1_options:
                        # If workflow requires DualCLIPLoader but no compatible models are available, fail
                        all_dual_clip = available_models.get("DualCLIPLoader", {})
                        all_clip1 = all_dual_clip.get("clip_name1", []) if isinstance(all_dual_clip, dict) else []
                        raise ValueError(
                            f"Required DualCLIPLoader clip_name1 '{current_clip1}' is not available. "
                            f"No compatible clip_name1 models found in ComfyUI for {model_type} workflow. "
                            f"Available clip_name1 models: {all_clip1}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif current_clip1 not in clip1_options:
                        new_clip1 = clip1_options[0]
                        logger.warning(
                            f"Node {node_id}: Replacing DualCLIPLoader clip_name1 '{current_clip1}' "
                            f"with '{new_clip1}' (not in available models: {clip1_options})"
                        )
                        inputs["clip_name1"] = new_clip1
                        fixes_applied.append(f"Node {node_id} clip_name1: {current_clip1} -> {new_clip1}")
                
                # Check clip_name2 - must check if input exists FIRST, then validate options
                if "clip_name2" in inputs:
                    current_clip2 = inputs.get("clip_name2")
                    if not clip2_options:
                        # If workflow requires DualCLIPLoader but no compatible models are available, fail
                        all_dual_clip = available_models.get("DualCLIPLoader", {})
                        all_clip2 = all_dual_clip.get("clip_name2", []) if isinstance(all_dual_clip, dict) else []
                        raise ValueError(
                            f"Required DualCLIPLoader clip_name2 '{current_clip2}' is not available. "
                            f"No compatible clip_name2 models found in ComfyUI for {model_type} workflow. "
                            f"Available clip_name2 models: {all_clip2}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif current_clip2 not in clip2_options:
                        new_clip2 = clip2_options[0]
                        logger.warning(
                            f"Node {node_id}: Replacing DualCLIPLoader clip_name2 '{current_clip2}' "
                            f"with '{new_clip2}' (not in available models: {clip2_options})"
                        )
                        inputs["clip_name2"] = new_clip2
                        fixes_applied.append(f"Node {node_id} clip_name2: {current_clip2} -> {new_clip2}")
            
            # Fix UNETLoader (Flux models)
            elif class_type == "UNETLoader":
                if model_type != "flux":
                    logger.warning(f"Node {node_id}: UNETLoader found but workflow type is {model_type} - may be incompatible")
                
                unet_options = available_models.get("UNETLoader") or []
                
                # Filter to compatible models only
                if model_type == "flux":
                    unet_options = [m for m in unet_options if is_model_compatible(m, "flux")]
                
                if "unet_name" in inputs:
                    current_unet = inputs.get("unet_name")
                    if not unet_options:
                        # If workflow requires UNETLoader but no compatible models are available, fail
                        all_unet_models = available_models.get("UNETLoader", [])
                        raise ValueError(
                            f"Required UNETLoader model '{current_unet}' is not available. "
                            f"No compatible UNETLoader models found in ComfyUI for {model_type} workflow. "
                            f"Available UNETLoader models: {all_unet_models}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif current_unet not in unet_options:
                        # Try to find matching model based on job model name
                        new_unet = None
                        
                        if job_model_name:
                            job_name_normalized = job_model_name.lower().replace("-", "").replace("_", "").replace(".", "")
                            for unet in unet_options:
                                unet_normalized = unet.lower().replace("-", "").replace("_", "").replace(".", "")
                                if job_name_normalized in unet_normalized or unet_normalized in job_name_normalized:
                                    new_unet = unet
                                    logger.info(f"Found matching UNETLoader model '{unet}' for job model '{job_model_name}'")
                                    break
                        
                        # Fall back to first available only if no match found
                        if not new_unet:
                            new_unet = unet_options[0]
                            logger.warning(f"No matching UNET for '{job_model_name}', using first available: {new_unet}")
                        
                        logger.warning(
                            f"Node {node_id}: Replacing UNETLoader unet_name '{current_unet}' "
                            f"with '{new_unet}' (available: {unet_options[:3]})"
                        )
                        inputs["unet_name"] = new_unet
                        fixes_applied.append(f"Node {node_id} unet_name: {current_unet} -> {new_unet}")
            
            # Fix VAELoader (Flux models)
            elif class_type == "VAELoader":
                if model_type != "flux":
                    logger.warning(f"Node {node_id}: VAELoader found but workflow type is {model_type} - may be incompatible")
                
                vae_options = available_models.get("VAELoader") or []
                
                # Filter to compatible models only
                if model_type == "flux":
                    vae_options = [m for m in vae_options if is_model_compatible(m, "flux")]
                
                if "vae_name" in inputs:
                    current_vae = inputs.get("vae_name")
                    if not vae_options:
                        # If workflow requires VAELoader but no compatible models are available, fail
                        all_vae_models = available_models.get("VAELoader", [])
                        raise ValueError(
                            f"Required VAELoader model '{current_vae}' is not available. "
                            f"No compatible VAELoader models found in ComfyUI for {model_type} workflow. "
                            f"Available VAELoader models: {all_vae_models}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif current_vae not in vae_options:
                        new_vae = vae_options[0]
                        logger.warning(
                            f"Node {node_id}: Replacing VAELoader vae_name '{current_vae}' "
                            f"with '{new_vae}' (not in available models: {vae_options})"
                        )
                        inputs["vae_name"] = new_vae
                        fixes_applied.append(f"Node {node_id} vae_name: {current_vae} -> {new_vae}")
            
            # Fix CheckpointLoaderSimple (SDXL/Flux checkpoint models)
            elif class_type == "CheckpointLoaderSimple":
                # Get checkpoint options from ComfyUI - use checkpoints key or fall back to CheckpointLoaderSimple
                ckpt_options = available_models.get("checkpoints") or available_models.get("CheckpointLoaderSimple") or []
                
                # Filter out FP8 models - they don't contain CLIP and won't work with CheckpointLoaderSimple
                # FP8 models need UNETLoader + DualCLIPLoader + VAELoader instead
                full_ckpt_options = [c for c in ckpt_options if "fp8" not in c.lower()]
                if full_ckpt_options:
                    logger.debug(f"Filtered to {len(full_ckpt_options)} full checkpoints (excluding FP8)")
                else:
                    # If no non-FP8 options, use all options (will likely fail but better than nothing)
                    full_ckpt_options = ckpt_options
                    logger.warning("No full checkpoints available (only FP8 models found)")
                
                if "ckpt_name" in inputs:
                    current_ckpt = inputs.get("ckpt_name")
                    # Check for placeholder values
                    placeholders = ["checkpoint_name.safetensors", "model.safetensors", "checkpoint.safetensors"]
                    is_placeholder = current_ckpt in placeholders
                    
                    if not full_ckpt_options:
                        # If workflow requires CheckpointLoaderSimple but no compatible models are available, fail
                        raise ValueError(
                            f"Required CheckpointLoaderSimple checkpoint '{current_ckpt}' is not available. "
                            f"No compatible checkpoint models found in ComfyUI for {model_type} workflow. "
                            f"Available checkpoint models: {ckpt_options}. "
                            f"Please ensure required model files are installed in the ComfyUI models directory."
                        )
                    elif is_placeholder or current_ckpt not in ckpt_options:
                        # Try to find best matching checkpoint based on job model name
                        new_ckpt = None
                        
                        if job_model_name:
                            # Normalize job model name for matching (remove fp8, krea, etc for base model matching)
                            job_base = job_model_name.lower()
                            # Extract base model name (e.g., "flux.1-krea-dev" -> look for "flux")
                            
                            # First, try exact substring match on full checkpoints
                            job_name_normalized = job_base.replace("-", "").replace("_", "").replace(".", "")
                            for ckpt in full_ckpt_options:
                                ckpt_normalized = ckpt.lower().replace("-", "").replace("_", "").replace(".", "")
                                if job_name_normalized in ckpt_normalized or ckpt_normalized in job_name_normalized:
                                    new_ckpt = ckpt
                                    logger.info(f"Found matching full checkpoint '{ckpt}' for job model '{job_model_name}'")
                                    break
                            
                            # Second, try base model matching (flux.1-krea-dev -> flux1-dev.safetensors)
                            if not new_ckpt:
                                # Extract base model keywords
                                base_keywords = ["flux", "sdxl", "sd", "chroma", "stable"]
                                for keyword in base_keywords:
                                    if keyword in job_base:
                                        for ckpt in full_ckpt_options:
                                            if keyword in ckpt.lower():
                                                new_ckpt = ckpt
                                                logger.info(f"Found base-model matching checkpoint '{ckpt}' for job model '{job_model_name}' (matched '{keyword}')")
                                                break
                                    if new_ckpt:
                                        break
                        
                        # Fall back to first available full checkpoint if no match found
                        if not new_ckpt:
                            new_ckpt = full_ckpt_options[0]
                            logger.warning(f"No matching checkpoint for '{job_model_name}', using first available full checkpoint")
                        
                        logger.warning(
                            f"Node {node_id}: Replacing CheckpointLoaderSimple ckpt_name '{current_ckpt}' "
                            f"with '{new_ckpt}' (available full checkpoints: {full_ckpt_options[:3]})"
                        )
                        inputs["ckpt_name"] = new_ckpt
                        fixes_applied.append(f"Node {node_id} ckpt_name: {current_ckpt} -> {new_ckpt}")
    
    if fixes_applied:
        logger.info(f"Applied {len(fixes_applied)} model filename fixes:")
        for fix in fixes_applied:
            logger.info(f"  - {fix}")
    else:
        logger.debug("All model filenames validated - no fixes needed")
    
    return fixed_workflow


def map_sampler_name(api_sampler: Optional[str]) -> Optional[str]:
    if not api_sampler:
        return api_sampler
    if api_sampler.startswith('k_'):
        return api_sampler[2:]
    return api_sampler


def map_wanvideo_scheduler(scheduler: Optional[str]) -> str:
    """Map scheduler values to valid WanVideoSampler schedulers.
    
    Valid schedulers: 'unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 
    'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 
    'lcm', 'lcm/beta', 'res_multistep', 'flowmatch_causvid', 'flowmatch_distill', 
    'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm'
    
    Default: 'unipc'
    """
    if not scheduler:
        return "unipc"
    
    scheduler_lower = scheduler.lower()
    
    # Valid schedulers - return as-is
    valid_schedulers = [
        'unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta',
        'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta',
        'res_multistep', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa',
        'multitalk', 'sa_ode_stable', 'rcm'
    ]
    
    if scheduler in valid_schedulers:
        return scheduler
    
    # Map invalid schedulers to valid ones
    scheduler_mapping = {
        'dpmpp_3m_sde_gpu': 'dpm++_sde',
        'dpmpp_3m_sde': 'dpm++_sde',
        'dpmpp_2m_sde': 'dpm++_sde',
        'dpmpp_sde': 'dpm++_sde',
        'dpmpp_2m': 'dpm++',
        'dpmpp_3m': 'dpm++',
        'dpm_2m': 'dpm++',
        'dpm_2m_sde': 'dpm++_sde',
        'normal': 'unipc',
        'karras': 'unipc',
        'simple': 'unipc',
        'exponential': 'unipc',
    }
    
    mapped = scheduler_mapping.get(scheduler_lower)
    if mapped:
        logger.warning(f"Mapped invalid WanVideo scheduler '{scheduler}' to '{mapped}'")
        return mapped
    
    # Default fallback
    logger.warning(f"Unknown WanVideo scheduler '{scheduler}', using default 'unipc'")
    return "unipc"


async def download_image(url: str, filename: str) -> str:
    # Download the image to a temporary file
    temp_dir = "/tmp/comfyui_inputs"
    os.makedirs(temp_dir, exist_ok=True)
    temp_filepath = os.path.join(temp_dir, filename)

    async with httpx.AsyncClient() as client:
        # Download the image
        response = await client.get(url)
        response.raise_for_status()

        with open(temp_filepath, "wb") as f:
            f.write(response.content)

        # Upload to ComfyUI via API
        upload_url = f"{Settings.COMFYUI_URL}/upload/image"
        with open(temp_filepath, "rb") as f:
            files = {"image": (filename, f, "image/png")}
            upload_response = await client.post(upload_url, files=files)
            upload_response.raise_for_status()

    logger.debug(f"Downloaded and uploaded image: {filename}")
    return filename


def load_workflow_file(workflow_filename: str) -> Dict[str, Any]:
    workflow_path = os.path.join(Settings.WORKFLOW_DIR, workflow_filename)

    if not os.path.exists(workflow_path):
        # Case-insensitive resolution fallback
        target_lower = workflow_filename.lower()
        try:
            for fname in os.listdir(Settings.WORKFLOW_DIR):
                if fname.lower() == target_lower:
                    workflow_path = os.path.join(Settings.WORKFLOW_DIR, fname)
                    break
        except FileNotFoundError:
            pass
        if not os.path.exists(workflow_path):
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Validate workflow has actual model file names, not placeholders
    _validate_workflow_model_names(data, workflow_filename)
    
    # Return a deep copy so callers can safely mutate without caching stale fields
    return copy.deepcopy(data)


def _validate_workflow_model_names(workflow: Dict[str, Any], filename: str) -> None:
    placeholders = ["checkpoint_name.safetensors", "model.safetensors", "checkpoint.safetensors"]
    model_fields = {
        "CheckpointLoaderSimple": "ckpt_name",
        "UNETLoader": "unet_name",
        "CLIPLoader": "clip_name",
        "VAELoader": "vae_name",
        "WanVideoModelLoader": "model",
        "WanVideoVAELoader": "model_name"
    }
    
    if isinstance(workflow, dict) and "nodes" in workflow:
        # ComfyUI native format - nodes array
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            class_type = node.get("type", "")
            if class_type in model_fields:
                # In ComfyUI native format, model names are in widgets_values[0], not inputs
                # inputs is always a list/array in ComfyUI native format, never a dict
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) > 0:
                    model_name = widgets[0]
                    if isinstance(model_name, str) and model_name in placeholders:
                        logger.warning(f"Workflow {filename} node {node.get('id')} has placeholder '{model_name}' - export from ComfyUI with actual model files")
    else:
        # Simple format - direct node objects
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            class_type = node_data.get("class_type", "")
            if class_type in model_fields:
                inputs = node_data.get("inputs", {})
                if isinstance(inputs, dict):
                    field_name = model_fields[class_type]
                    model_name = inputs.get(field_name, "")
                    if isinstance(model_name, str) and model_name in placeholders:
                        logger.warning(f"Workflow {filename} node {node_id} has placeholder '{model_name}' - export from ComfyUI with actual model files")


async def process_workflow(
    workflow: Dict[str, Any], job: Dict[str, Any]
) -> Dict[str, Any]:
    payload = job.get("payload", {})
    seed = generate_seed(payload.get("seed"))
    
    # Debug logging
    logger.debug(f"Job payload: {payload}")
    logger.debug(f"Job prompt: {payload.get('prompt')}")
    logger.debug(f"Job negative_prompt: {payload.get('negative_prompt')}")

    # Make a deep copy to avoid modifying the original
    processed_workflow = copy.deepcopy(workflow)
    model_type = detect_workflow_model_type(processed_workflow)
    if model_type == "unknown":
        model_name_lower = (job.get("model") or "").lower()
        if "wan" in model_name_lower:
            model_type = "wanvideo"
        elif "flux" in model_name_lower:
            model_type = "flux"
        elif "sdxl" in model_name_lower or "xl" in model_name_lower:
            model_type = "sdxl"
    logger.debug(f"Processing workflow model type: {model_type}")
    _force_video_processing(job, model_type)

    # Handle source image for img2img workflows
    source_image_filename = None
    if (
        job.get("source_image")
        and job.get("source_processing") == "img2img"
    ):
        # Generate unique filename
        image_ext = "png"  # Default, could be improved to detect from URL
        source_image_filename = (
            f"horde_input_{job.get('id', 'unknown')}_{uuid.uuid4().hex[:8]}.{image_ext}"
        )

        try:
            await download_image(job["source_image"], source_image_filename)
            logger.debug(f"Downloaded source image: {source_image_filename}")
        except Exception as e:
            logger.warning(f"Failed to download source image: {e}")
            source_image_filename = None
    else:
        logger.debug("Skipping image download - this is a text-to-image job")

    # Update LoadImageOutput nodes for img2img jobs
    if job.get("source_processing") == "img2img" and source_image_filename:
        processed_workflow = update_loadimageoutput_nodes(processed_workflow, source_image_filename)

    # Pre-calculate commonly reused payload fields
    # NOTE: steps and cfg are intentionally NOT read from payload - we always use workflow defaults
    # payload_steps and payload_cfg are set to None below to ensure workflow values are used
    # WORKFLOW FILE IS SOURCE OF TRUTH
    # Never override workflow values with payload values - workflow files have optimized settings
    # Only prompt, seed, and dimensions come from payload
    payload_steps = None
    payload_cfg = None
    payload_sampler = None
    payload_scheduler = None
    payload_denoise = None
    logger.debug(f"Using workflow defaults for all KSampler parameters (steps, cfg, sampler, scheduler, denoise)")

    def _apply_ksampler_dict(inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Only apply steps if payload value is higher than workflow default
        if payload_steps is not None and "steps" in inputs:
            current_steps = inputs.get("steps")
            if current_steps is None or payload_steps >= current_steps:
                inputs["steps"] = payload_steps
            else:
                logger.warning(f"KSampler: Ignoring payload steps {payload_steps} (workflow default {current_steps} is higher)")
        # Only apply cfg if payload value is higher than workflow default
        if payload_cfg is not None:
            if "cfg" in inputs:
                current_cfg = inputs.get("cfg")
                if current_cfg is None or payload_cfg >= current_cfg:
                    inputs["cfg"] = payload_cfg
                else:
                    logger.warning(f"KSampler: Ignoring payload cfg {payload_cfg} (workflow default {current_cfg} is higher)")
            elif "cfg_scale" in inputs:
                current_cfg = inputs.get("cfg_scale")
                if current_cfg is None or payload_cfg >= current_cfg:
                    inputs["cfg_scale"] = payload_cfg
                else:
                    logger.warning(f"KSampler: Ignoring payload cfg_scale {payload_cfg} (workflow default {current_cfg} is higher)")
        if payload_sampler:
            inputs["sampler_name"] = payload_sampler
        if payload_scheduler and "scheduler" in inputs:
            inputs["scheduler"] = payload_scheduler
        if payload_denoise is not None and "denoise" in inputs:
            inputs["denoise"] = payload_denoise
        if payload.get("clip_skip") is not None and "clip_skip" in inputs:
            inputs["clip_skip"] = payload.get("clip_skip")
        return inputs

    def _apply_ksampler_widgets(widgets: list) -> list:
        if not isinstance(widgets, list):
            return widgets
        # seed is handled elsewhere; respect only advanced params here
        # Only apply steps if payload value is higher than workflow default
        if payload_steps is not None and len(widgets) >= 2:
            current_steps = widgets[1] if len(widgets) > 1 else None
            if current_steps is None or payload_steps >= current_steps:
                widgets[1] = payload_steps
            else:
                logger.warning(f"KSampler widgets: Ignoring payload steps {payload_steps} (workflow default {current_steps} is higher)")
        # Only apply cfg if payload value is higher than workflow default
        if payload_cfg is not None and len(widgets) >= 3:
            current_cfg = widgets[2] if len(widgets) > 2 else None
            if current_cfg is None or payload_cfg >= current_cfg:
                widgets[2] = payload_cfg
            else:
                logger.warning(f"KSampler widgets: Ignoring payload cfg {payload_cfg} (workflow default {current_cfg} is higher)")
        if payload_sampler and len(widgets) >= 4:
            widgets[3] = payload_sampler
        if payload_scheduler and len(widgets) >= 5:
            widgets[4] = payload_scheduler
        if payload_denoise is not None and len(widgets) >= 6:
            widgets[5] = payload_denoise
        return widgets

    # Process each node in the workflow
    # Handle ComfyUI format (nodes array)
    if isinstance(processed_workflow, dict) and "nodes" in processed_workflow:
        logger.info("Processing workflow in ComfyUI native format (nodes array)")
        nodes = processed_workflow.get("nodes", [])
        # Don't modify WanVideo workflows - they work correctly as-is
        for node in nodes:
            if not isinstance(node, dict):
                continue

            # In ComfyUI native format, inputs is typically a list, and most editable
            # parameters live in widgets_values. Avoid dict-style indexing on lists.
            inputs = node.get("inputs", [])
            widgets = node.get("widgets_values", [])
            class_type = node.get("type")  # ComfyUI uses "type" instead of "class_type"

            # Handle LoadImage nodes for source images (set via widgets_values)
            if class_type == "LoadImage":
                if source_image_filename:
                    if isinstance(widgets, list) and len(widgets) >= 1:
                        widgets[0] = source_image_filename
                        node["widgets_values"] = widgets
                    else:
                        node["widgets_values"] = [source_image_filename]
                else:
                    # Default placeholder
                    if isinstance(widgets, list) and len(widgets) >= 1:
                        widgets[0] = "example.png"
                        node["widgets_values"] = widgets
                    else:
                        node["widgets_values"] = ["example.png"]

            # Handle KSampler nodes - only update seed in widgets_values index 0
            elif class_type in ["KSampler", "KSamplerAdvanced"]:
                if isinstance(widgets, list) and len(widgets) >= 1:
                    widgets[0] = seed
                    node["widgets_values"] = _apply_ksampler_widgets(widgets)
                # Some native-format exports still expose dict inputs for ksamp config
                if isinstance(inputs, dict):
                    node["inputs"] = _apply_ksampler_dict(inputs)

            # Handle text encoding nodes - properly handle positive vs negative prompts
            elif class_type == "CLIPTextEncode":
                # In native format, prompt text is in widgets_values[0]. Use node title to infer pos/neg.
                title = node.get("title", "") or ""
                if isinstance(widgets, list) and len(widgets) >= 1:
                    if "negative" in title.lower():
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            widgets[0] = neg
                            logger.debug(f"Updated negative prompt: {neg}")
                    elif "positive" in title.lower():
                        # This is a positive prompt node
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos:
                            widgets[0] = pos
                            logger.debug(f"Updated positive prompt: {pos}")
                    else:
                        # If title doesn't specify, check if we have a prompt and this looks like a positive node
                        # (most CLIPTextEncode nodes are positive unless explicitly marked negative)
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos and not payload.get("negative_prompt"):
                            widgets[0] = pos
                            logger.debug(f"Updated unspecified prompt node with positive: {pos}")
                    node["widgets_values"] = widgets

            # Handle latent image nodes - update dimensions via widgets_values [width, height]
            elif class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                w = payload.get("width")
                h = payload.get("height")
                if isinstance(widgets, list):
                    if w and len(widgets) >= 1:
                        widgets[0] = w
                    if h and len(widgets) >= 2:
                        widgets[1] = h
                    node["widgets_values"] = widgets
            # Handle video latent nodes - update dimensions and length via widgets_values [width, height, length]
            elif class_type == "EmptyHunyuanLatentVideo":
                w = payload.get("width")
                h = payload.get("height")
                # Length can be specified directly or via the length parameter (from styles.json)
                length = payload.get("length", payload.get("video_length", 81))  # Default to 81 if not specified
                if isinstance(widgets, list):
                    if w and len(widgets) >= 1:
                        widgets[0] = w
                    if h and len(widgets) >= 2:
                        widgets[1] = h
                    if len(widgets) >= 3:
                        widgets[2] = length
                    node["widgets_values"] = widgets
                logger.debug(f"Updated video parameters: width={w}, height={h}, length={length}")

            # Handle save image nodes - update filename prefix for job tracking
            elif class_type == "SaveImage":
                job_id = job.get("id", "unknown")
                if isinstance(widgets, list) and len(widgets) >= 1:
                    widgets[0] = f"horde_{job_id}"
                    node["widgets_values"] = widgets
                    
            # Handle save video nodes - update filename prefix for job tracking
            elif class_type == "SaveVideo":
                job_id = job.get("id", "unknown")
                if isinstance(widgets, list) and len(widgets) >= 1:
                    widgets[0] = f"horde_{job_id}"
                    node["widgets_values"] = widgets
                    
            # Handle CreateVideo node - update fps if specified
            elif class_type == "CreateVideo":
                fps = payload.get("fps")
                if isinstance(widgets, list) and len(widgets) >= 1 and fps:
                    widgets[0] = fps
                    node["widgets_values"] = widgets
                    logger.debug(f"Updated CreateVideo node fps to {fps}")
            
            # Handle UNETLoader nodes - model filename is in widgets_values[0] for ComfyUI native format
            elif class_type == "UNETLoader":
                # UNETLoader model filename is in widgets_values[0]
                # The workflow files already have the correct model names, so we don't need to change them
                # But we should validate they exist if needed
                if isinstance(widgets, list) and len(widgets) >= 1:
                    current_model = widgets[0]
                    logger.debug(f"UNETLoader node {node.get('id')}: Using model '{current_model}'")
                    # Keep the existing model name from the workflow
                    node["widgets_values"] = widgets
            
            # Handle WanVideoSampler nodes - validate scheduler and apply parameters (ComfyUI native format)
            elif class_type == "WanVideoSampler":
                # In native format, scheduler might be in inputs dict
                if isinstance(inputs, dict):
                    node_id_str = str(node.get('id', 'unknown'))

                    # Apply scheduler from payload if provided, otherwise validate workflow scheduler
                    if payload_scheduler and "scheduler" in inputs:
                        valid_scheduler = map_wanvideo_scheduler(payload_scheduler)
                        logger.info(f"Node {node_id_str}: Applying scheduler from payload: '{payload_scheduler}' -> '{valid_scheduler}'")
                        inputs["scheduler"] = valid_scheduler
                    elif "scheduler" in inputs:
                        current_scheduler = inputs.get("scheduler")
                        valid_scheduler = map_wanvideo_scheduler(current_scheduler)
                        if current_scheduler != valid_scheduler:
                            logger.info(f"Node {node_id_str}: Validating workflow scheduler: '{current_scheduler}' -> '{valid_scheduler}'")
                            inputs["scheduler"] = valid_scheduler

                    # Apply parameters from payload - only if they're reasonable
                    if payload_steps is not None and "steps" in inputs:
                        old_steps = inputs.get("steps")
                        # Only apply if payload steps is higher than workflow default
                        if old_steps is None or payload_steps >= old_steps:
                            inputs["steps"] = payload_steps
                            logger.info(f"Node {node_id_str}: Applied steps: {old_steps} -> {payload_steps}")
                        else:
                            logger.warning(f"Node {node_id_str}: Ignoring payload steps {payload_steps} (workflow default {old_steps} is higher)")
                    if payload_cfg is not None and "cfg" in inputs:
                        old_cfg = inputs.get("cfg")
                        # Only apply if payload cfg is higher than workflow default
                        if old_cfg is None or payload_cfg >= old_cfg:
                            inputs["cfg"] = payload_cfg
                            logger.info(f"Node {node_id_str}: Applied cfg: {old_cfg} -> {payload_cfg}")
                        else:
                            logger.warning(f"Node {node_id_str}: Ignoring payload cfg {payload_cfg} (workflow default {old_cfg} is higher)")
                    if payload.get("shift") is not None and "shift" in inputs:
                        old_shift = inputs.get("shift")
                        inputs["shift"] = payload.get("shift")
                        logger.info(f"Node {node_id_str}: Applied shift: {old_shift} -> {payload.get('shift')}")
                    if payload.get("riflex_freq_index") is not None and "riflex_freq_index" in inputs:
                        old_riflex = inputs.get("riflex_freq_index")
                        inputs["riflex_freq_index"] = payload.get("riflex_freq_index")
                        logger.info(f"Node {node_id_str}: Applied riflex_freq_index: {old_riflex} -> {payload.get('riflex_freq_index')}")

                    node["inputs"] = inputs

            # Handle WanVideoDecode nodes - prevent payload parameters from causing tensor mismatches
            elif class_type == "WanVideoDecode":
                logger.info(f"Processing WanVideoDecode node {node.get('id', 'unknown')} in native format")
                # WanVideoDecode tile parameters should NOT be overridden by payload width/height
                # as they need to match the WanVideoSampler output tensor dimensions
                if isinstance(inputs, dict):
                    node_id_str = str(node.get('id', 'unknown'))
                    # Log current tile settings for debugging tensor dimension issues
                    tile_x = inputs.get("tile_x")
                    tile_y = inputs.get("tile_y")
                    logger.info(f"WanVideoDecode node {node_id_str}: tile_x={tile_x}, tile_y={tile_y}")
                    # Keep workflow tile settings - do not override with payload width/height
                    node["inputs"] = inputs
            
            # Handle BasicScheduler nodes - update steps and scheduler via widgets_values
            elif class_type == "BasicScheduler":
                # BasicScheduler widgets_values: [scheduler, steps, denoise]
                if isinstance(widgets, list) and len(widgets) >= 3:
                    current_steps = widgets[1] if len(widgets) > 1 else None
                    scheduler_value = widgets[0] if widgets else None

                    # Only adjust scheduler for non-WanVideo workflows. WanVideo pipelines manage
                    # schedulers inside their dedicated sampler nodes.
                    if model_type != "wanvideo":
                        valid_basic_schedulers = [
                            "simple", "sgm_uniform", "karras", "exponential",
                            "ddim_uniform", "beta", "normal", "linear_quadratic",
                            "kl_optimal"
                        ]
                        if payload_scheduler:
                            if payload_scheduler in valid_basic_schedulers:
                                widgets[0] = payload_scheduler
                                logger.debug(f"BasicScheduler node {node.get('id')}: Applied scheduler '{payload_scheduler}'")
                            else:
                                logger.warning(
                                    f"BasicScheduler node {node.get('id')}: Ignoring unsupported scheduler '{payload_scheduler}'"
                                )
                        elif scheduler_value not in valid_basic_schedulers:
                            logger.warning(
                                f"BasicScheduler node {node.get('id')}: Scheduler '{scheduler_value}' not supported by BasicScheduler, defaulting to 'simple'"
                            )
                            widgets[0] = "simple"

                    # Only apply steps if payload value is reasonable and higher than current
                    if payload_steps is not None:
                        if current_steps is None or payload_steps >= current_steps:
                            widgets[1] = payload_steps
                            logger.info(f"BasicScheduler node {node.get('id')}: Updated steps from {current_steps} to {payload_steps}")
                        else:
                            logger.warning(f"BasicScheduler node {node.get('id')}: Ignoring payload steps {payload_steps} (workflow default {current_steps} is higher)")
                    node["widgets_values"] = widgets
            
            # Handle SamplerCustom nodes - update cfg via widgets_values
            elif class_type == "SamplerCustom":
                # SamplerCustom widgets_values: [add_noise, noise_seed, seed_type, cfg]
                if isinstance(widgets, list) and len(widgets) >= 4:
                    current_cfg = widgets[3] if len(widgets) > 3 else None
                    # Only apply cfg if payload value is reasonable and higher than current
                    if payload_cfg is not None:
                        if current_cfg is None or payload_cfg >= current_cfg:
                            widgets[3] = payload_cfg
                            logger.info(f"SamplerCustom node {node.get('id')}: Updated cfg from {current_cfg} to {payload_cfg}")
                        else:
                            logger.warning(f"SamplerCustom node {node.get('id')}: Ignoring payload cfg {payload_cfg} (workflow default {current_cfg} is higher)")
                if isinstance(widgets, list) and len(widgets) >= 2:
                    widgets[1] = seed  # Update noise_seed
                    node["widgets_values"] = widgets
            
            # Handle WanVideoEmptyEmbeds nodes - ALWAYS use workflow defaults (ComfyUI native format)
            elif class_type == "WanVideoEmptyEmbeds":
                if isinstance(inputs, dict):
                    # IMPORTANT: Always use workflow defaults for WAN video dimensions
                    # The workflow is carefully designed with specific width/height/num_frames
                    # that must match the WanVideoDecode tiling parameters to avoid tensor mismatches
                    # DO NOT apply payload width/height/num_frames - they cause decoding errors
                    logger.info(f"WanVideoEmptyEmbeds: Using workflow defaults - width={inputs.get('width')}, height={inputs.get('height')}, frames={inputs.get('num_frames')}")
                    node["inputs"] = inputs

            # Handle LoadImageOutput nodes for source images
            elif class_type == "LoadImageOutput":
                if source_image_filename:
                    if isinstance(widgets, list) and len(widgets) >= 1:
                        widgets[0] = source_image_filename
                        node["widgets_values"] = widgets
                        logger.debug(f"Updated LoadImageOutput node {node.get('id')} to use: {source_image_filename}")
                    else:
                        node["widgets_values"] = [source_image_filename]
                        logger.debug(f"Created widgets_values for LoadImageOutput node {node.get('id')}: {source_image_filename}")

    # Handle simple format (direct node objects)
    else:
        logger.info("Processing workflow in simple format (node objects)")
        for node_id, node_data in processed_workflow.items():
            if not isinstance(node_data, dict):
                continue

            inputs = node_data.get("inputs", {})
            class_type = node_data.get("class_type", "")

            # Handle LoadImage nodes for source images
            if class_type == "LoadImage":
                if source_image_filename:
                    inputs["image"] = source_image_filename
                else:
                    # If no source image, use a default or skip this workflow
                    inputs["image"] = "example.png"  # Default placeholder

            # Handle KSampler nodes - only update seed, preserve all other settings
            elif class_type in ["KSampler", "KSamplerAdvanced"]:
                if "seed" in inputs:
                    inputs["seed"] = seed
                if "noise_seed" in inputs:
                    inputs["noise_seed"] = seed
                inputs = _apply_ksampler_dict(inputs)
                node_data["inputs"] = inputs

            # Handle text encoding nodes - properly handle positive vs negative prompts
            elif class_type == "CLIPTextEncode":
                if "text" in inputs:
                    current_text = inputs.get("text", "")
                    logger.info(f"Processing CLIPTextEncode node {node_id}, current text: '{current_text[:50]}...'")
                    logger.info(f"Payload prompt: '{payload.get('prompt', 'NOT PROVIDED')[:50]}...', negative: '{payload.get('negative_prompt', 'NOT PROVIDED')[:50]}...'")
                    # First, find which KSampler nodes this CLIPTextEncode connects to
                    is_negative_prompt = False
                    is_positive_prompt = False
                    
                    # Check all KSampler nodes to see if this CLIPTextEncode is connected to negative input
                    for ks_id, ks_data in processed_workflow.items():
                        if isinstance(ks_data, dict) and ks_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                            ks_inputs = ks_data.get("inputs", {})
                            if "negative" in ks_inputs:
                                neg_ref = ks_inputs["negative"]
                                if isinstance(neg_ref, list) and len(neg_ref) > 0 and str(neg_ref[0]) == str(node_id):
                                    is_negative_prompt = True
                                    logger.info(f"Node {node_id} identified as negative prompt (connected to KSampler {ks_id} negative input)")
                                    break
                    
                    # If not negative, check if it's connected to positive input (directly or via FluxGuidance)
                    if not is_negative_prompt:
                        for ks_id, ks_data in processed_workflow.items():
                            if isinstance(ks_data, dict) and ks_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                                ks_inputs = ks_data.get("inputs", {})
                                if "positive" in ks_inputs:
                                    pos_ref = ks_inputs["positive"]
                                    logger.info(f"Checking KSampler {ks_id}: positive ref={pos_ref}, node_id={node_id}")
                                    
                                    # Direct connection check
                                    if isinstance(pos_ref, list) and len(pos_ref) > 0 and str(pos_ref[0]) == str(node_id):
                                        is_positive_prompt = True
                                        logger.info(f"Node {node_id} identified as positive prompt (connected to KSampler {ks_id} positive input)")
                                        break
                                    
                                    # Check through FluxGuidance intermediary
                                    if isinstance(pos_ref, list) and len(pos_ref) > 0:
                                        intermediate_node_id = str(pos_ref[0])
                                        intermediate_node = processed_workflow.get(intermediate_node_id, {})
                                        if isinstance(intermediate_node, dict) and intermediate_node.get("class_type") == "FluxGuidance":
                                            fg_inputs = intermediate_node.get("inputs", {})
                                            cond_ref = fg_inputs.get("conditioning")
                                            logger.info(f"Found FluxGuidance {intermediate_node_id}, conditioning ref={cond_ref}")
                                            if isinstance(cond_ref, list) and len(cond_ref) > 0 and str(cond_ref[0]) == str(node_id):
                                                is_positive_prompt = True
                                                logger.info(f"Node {node_id} identified as positive prompt (via FluxGuidance {intermediate_node_id} -> KSampler {ks_id})")
                                                break
                    
                    # Now handle the prompt based on connection type
                    if is_negative_prompt:
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            inputs["text"] = neg
                            logger.info(f"Node {node_id}: Updated negative prompt: {neg[:50]}...")
                        else:
                            logger.info(f"Node {node_id}: Keeping workflow default negative prompt: {inputs.get('text', '')[:50]}...")
                    elif is_positive_prompt:
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos:
                            old_text = inputs.get("text", "")
                            inputs["text"] = pos
                            logger.info(f"Node {node_id}: Updated positive prompt from '{old_text[:30]}...' to '{pos[:50]}...'")
                            logger.info(f"Node {node_id}: Final positive prompt value: '{inputs.get('text', '')}'")
                        else:
                            logger.warning(f"Node {node_id}: No prompt provided in payload, keeping workflow default: {inputs.get('text', '')[:50]}...")
                            logger.info(f"Node {node_id}: Final positive prompt value (using default): '{inputs.get('text', '')}'")
                    else:
                        # Fallback: use _meta title if connection analysis failed
                        meta = node_data.get("_meta", {})
                        title = meta.get("title", "").lower()
                        
                        logger.info(f"Node {node_id}: Connection detection failed, using title fallback. Title: '{title}'")
                        
                        if "negative" in title:
                            neg = payload.get("negative_prompt")
                            if isinstance(neg, str) and neg:
                                inputs["text"] = neg
                                logger.info(f"Node {node_id}: Updated negative prompt by title fallback: {neg[:50]}...")
                            else:
                                logger.info(f"Node {node_id}: Keeping workflow default negative prompt by title: {inputs.get('text', '')[:50]}...")
                        elif "positive" in title:
                            # Explicitly check for positive in title
                            pos = payload.get("prompt")
                            if isinstance(pos, str) and pos:
                                old_text = inputs.get("text", "")
                                inputs["text"] = pos
                                logger.info(f"Node {node_id}: Updated positive prompt by title fallback from '{old_text[:30]}...' to '{pos[:50]}...'")
                                logger.info(f"Node {node_id}: Final positive prompt value: '{inputs.get('text', '')}'")
                            else:
                                logger.warning(f"Node {node_id}: No prompt provided for positive node, keeping workflow default: {inputs.get('text', '')[:50]}...")
                                logger.info(f"Node {node_id}: Final positive prompt value (using default): '{inputs.get('text', '')}'")
                        else:
                            # Assume positive for any other CLIPTextEncode nodes (most are positive)
                            pos = payload.get("prompt")
                            if isinstance(pos, str) and pos:
                                old_text = inputs.get("text", "")
                                inputs["text"] = pos
                                logger.info(f"Node {node_id}: Updated unspecified prompt (assumed positive) from '{old_text[:30]}...' to '{pos[:50]}...'")
                                logger.info(f"Node {node_id}: Final positive prompt value: '{inputs.get('text', '')}'")
                            else:
                                logger.warning(f"Node {node_id}: No prompt provided, keeping workflow default: {inputs.get('text', '')[:50]}...")
                                logger.info(f"Node {node_id}: Final positive prompt value (using default): '{inputs.get('text', '')}'")

            # Handle latent image nodes - only update dimensions if specified
            elif class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                if "width" in inputs and payload.get("width"):
                    inputs["width"] = payload.get("width")
                if "height" in inputs and payload.get("height"):
                    inputs["height"] = payload.get("height")
            # Handle video latent nodes - update dimensions and length
            elif class_type == "EmptyHunyuanLatentVideo":
                if "width" in inputs and payload.get("width"):
                    inputs["width"] = payload.get("width")
                if "height" in inputs and payload.get("height"):
                    inputs["height"] = payload.get("height")
                if "length" in inputs:
                    # Length can be specified directly or via the length parameter (from styles.json)
                    inputs["length"] = payload.get("length", payload.get("video_length", 81))  # Default to 81 frames if not specified
                # Check for fps in the CreateVideo node
                if "fps" in inputs and payload.get("fps"):
                    inputs["fps"] = payload.get("fps")
                logger.debug(f"Updated EmptyHunyuanLatentVideo node with dimensions: {inputs.get('width')}x{inputs.get('height')}, length: {inputs.get('length')}")
            
            # Handle Wan22ImageToVideoLatent nodes - update dimensions and length for text-to-video
            elif class_type == "Wan22ImageToVideoLatent":
                if "width" in inputs and payload.get("width"):
                    inputs["width"] = payload.get("width")
                if "height" in inputs and payload.get("height"):
                    inputs["height"] = payload.get("height")
                if "length" in inputs:
                    # Length can be specified directly or via the length parameter (from styles.json)
                    # Convert video_length (in frames) to length parameter if needed
                    video_length = payload.get("length", payload.get("video_length"))
                    if video_length:
                        inputs["length"] = video_length
                logger.debug(f"Updated Wan22ImageToVideoLatent node {node_id} with dimensions: {inputs.get('width')}x{inputs.get('height')}, length: {inputs.get('length')}")

            # Handle save image nodes - update filename prefix for job tracking
            elif class_type == "SaveImage":
                if "filename_prefix" in inputs:
                    job_id = job.get("id", "unknown")
                    inputs["filename_prefix"] = f"horde_{job_id}"
                    
            # Handle save video nodes - update filename prefix for job tracking
            elif class_type == "SaveVideo":
                if "filename_prefix" in inputs:
                    job_id = job.get("id", "unknown")
                    inputs["filename_prefix"] = f"horde_{job_id}"
                    
            # Handle CreateVideo node - update fps if specified
            elif class_type == "CreateVideo":
                if "fps" in inputs and payload.get("fps"):
                    inputs["fps"] = payload.get("fps")
                    logger.debug(f"Updated CreateVideo node fps to {inputs['fps']}")

            # Handle LoadImageOutput nodes for source images
            elif class_type == "LoadImageOutput":
                if source_image_filename and "image" in inputs:
                    inputs["image"] = source_image_filename
                    logger.debug(f"Updated LoadImageOutput node {node_id} to use: {source_image_filename}")
            
            # Handle WanVideoSampler nodes - validate scheduler and apply parameters
            elif class_type == "WanVideoSampler":
                # Apply scheduler from payload if provided, otherwise validate workflow scheduler
                if payload_scheduler and "scheduler" in inputs:
                    valid_scheduler = map_wanvideo_scheduler(payload_scheduler)
                    logger.info(f"Node {node_id}: Applying scheduler from payload: '{payload_scheduler}' -> '{valid_scheduler}'")
                    inputs["scheduler"] = valid_scheduler
                elif "scheduler" in inputs:
                    # Validate workflow's scheduler even if payload doesn't provide one
                    current_scheduler = inputs.get("scheduler")
                    valid_scheduler = map_wanvideo_scheduler(current_scheduler)
                    if current_scheduler != valid_scheduler:
                        logger.info(f"Node {node_id}: Validating workflow scheduler: '{current_scheduler}' -> '{valid_scheduler}'")
                        inputs["scheduler"] = valid_scheduler
                
                # Apply parameters from payload (only override if provided)
                if payload_steps is not None and "steps" in inputs:
                    old_steps = inputs.get("steps")
                    inputs["steps"] = payload_steps
                    logger.info(f"Node {node_id}: Applied steps: {old_steps} -> {payload_steps}")
                if payload_cfg is not None and "cfg" in inputs:
                    old_cfg = inputs.get("cfg")
                    inputs["cfg"] = payload_cfg
                    logger.info(f"Node {node_id}: Applied cfg: {old_cfg} -> {payload_cfg}")
                if "seed" in inputs:
                    inputs["seed"] = seed
                if payload.get("shift") is not None and "shift" in inputs:
                    old_shift = inputs.get("shift")
                    inputs["shift"] = payload.get("shift")
                    logger.info(f"Node {node_id}: Applied shift: {old_shift} -> {payload.get('shift')}")
                if payload.get("riflex_freq_index") is not None and "riflex_freq_index" in inputs:
                    old_riflex = inputs.get("riflex_freq_index")
                    inputs["riflex_freq_index"] = payload.get("riflex_freq_index")
                    logger.info(f"Node {node_id}: Applied riflex_freq_index: {old_riflex} -> {payload.get('riflex_freq_index')}")
                node_data["inputs"] = inputs

            # Handle WanVideoDecode nodes - prevent payload parameters from causing tensor mismatches
            elif class_type == "WanVideoDecode":
                logger.info(f"Processing WanVideoDecode node {node_id} in simple format")
                # WanVideoDecode tile parameters should NOT be overridden by payload width/height
                # as they need to match the WanVideoSampler output tensor dimensions
                node_id_str = str(node_id)
                # Log current tile settings for debugging tensor dimension issues
                tile_x = inputs.get("tile_x")
                tile_y = inputs.get("tile_y")
                logger.info(f"WanVideoDecode node {node_id_str}: tile_x={tile_x}, tile_y={tile_y}")
                # Keep workflow tile settings - do not override with payload width/height
                node_data["inputs"] = inputs

            # Handle WanVideoEmptyEmbeds nodes - ALWAYS use workflow defaults
            # NOTE: Text-to-video models (t2v) don't support img2img properly.
            # Only image-to-video models (ti2v) can handle source images.
            elif class_type == "WanVideoEmptyEmbeds":
                # Check if this is an img2img job - warn but continue with workflow defaults
                if job.get("source_processing") == "img2img" and source_image_filename:
                    model_name = job.get("model", "").lower()
                    if "t2v" in model_name and "ti2v" not in model_name:
                        logger.warning(
                            f"Model {job.get('model')} is text-to-video only (t2v), not image-to-video (ti2v). "
                            f"Ignoring source image and using empty embeddings for text-to-video generation."
                        )
                    else:
                        logger.warning(
                            f"img2img requested for WanVideo model, but WanVideoEmptyEmbeds cannot be "
                            f"converted to image embeddings. Using empty embeddings (text-to-video mode)."
                        )
                
                # IMPORTANT: Always use workflow defaults for WAN video dimensions
                # The workflow is carefully designed with specific width/height/num_frames
                # that must match the WanVideoDecode tiling parameters to avoid tensor mismatches
                # DO NOT apply payload width/height/num_frames - they cause decoding errors
                logger.info(f"Node {node_id} WanVideoEmptyEmbeds: Using workflow defaults - width={inputs.get('width')}, height={inputs.get('height')}, frames={inputs.get('num_frames')}")
                node_data["inputs"] = inputs

    return processed_workflow


def convert_native_workflow_to_simple(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert ComfyUI native workflow format (nodes array + links) to the simple prompt format.
    This is required because the /prompt API expects the simple format.
    """
    if not isinstance(workflow, Dict) or "nodes" not in workflow:
        return workflow

    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])

    # Build lookup for link_id -> (source_node_id, source_slot_index)
    link_map: Dict[Any, Tuple[str, int]] = {}
    for link in links:
        if not isinstance(link, list) or len(link) < 4:
            continue
        link_id = link[0]
        from_node = link[1]
        from_slot = link[2]
        link_map[link_id] = (str(from_node), from_slot)

    simple_prompt: Dict[str, Dict[str, Any]] = {}
    skip_node_types = {"Note"}

    for node in nodes:
        if not isinstance(node, dict):
            continue

        node_id = node.get("id")
        if node_id is None:
            continue
        node_id_str = str(node_id)
        class_type = node.get("type")

        if class_type in skip_node_types:
            logger.debug(f"Skipping utility node '{class_type}' with id {node_id_str}")
            continue

        node_inputs: Dict[str, Any] = {}
        widgets_values = node.get("widgets_values", [])
        widget_index = 0

        for input_entry in node.get("inputs", []):
            if not isinstance(input_entry, dict):
                continue

            input_name = input_entry.get("name")
            if not input_name:
                continue

            link_id = input_entry.get("link")
            if link_id is not None and link_id in link_map:
                node_inputs[input_name] = [link_map[link_id][0], link_map[link_id][1]]
                continue

            # If the input is not linked, attempt to pull from widgets_values
            if widget_index < len(widgets_values):
                node_inputs[input_name] = widgets_values[widget_index]
                widget_index += 1
            else:
                # Fall back to default value if provided
                node_inputs[input_name] = input_entry.get("value")

        simple_prompt[node_id_str] = {
            "class_type": class_type,
            "inputs": node_inputs,
        }

        if "_meta" in node:
            simple_prompt[node_id_str]["_meta"] = node["_meta"]

    return simple_prompt


async def build_workflow(job: Dict[str, Any]) -> Dict[str, Any]:
    model_name = job.get("model", "")
    source_processing = job.get("source_processing", "txt2img")

    # Use the mapped workflow for all jobs (the mapper handles the logic)
    workflow_filename = get_workflow_file(model_name)
    
    # Validate that we have a proper workflow mapping
    if not workflow_filename:
        error_msg = f"No workflow mapping found for model: {model_name}"
        if Settings.WORKFLOW_FILE:
            error_msg += f" (Available workflows: {Settings.WORKFLOW_FILE})"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info(f"Loading workflow: {workflow_filename} for model: {model_name} (type: {source_processing})")
    
    try:
        workflow = load_workflow_file(workflow_filename)
        return await process_workflow(workflow, job)
    except Exception as e:
        logger.error(f"Error loading workflow {workflow_filename}: {e}")
        raise RuntimeError(f"Failed to load workflow {workflow_filename} for model {model_name}: {e}")


def convert_to_img2img(workflow: Dict[str, Any], source_image_filename: str) -> Dict[str, Any]:
    # Find the next available node ID
    max_node_id = max(int(k) for k in workflow.keys() if k.isdigit())
    
    # Find VAE node for reference
    vae_node_id = None
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "VAELoader":
            vae_node_id = node_id
            break
    
    # Find EmptySD3LatentImage nodes and replace them
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue
            
        if node_data.get("class_type") in ["EmptyLatentImage", "EmptySD3LatentImage"]:
            # Create LoadImage node
            load_image_id = str(max_node_id + 1)
            workflow[load_image_id] = {
                "inputs": {
                    "image": source_image_filename
                },
                "class_type": "LoadImage",
                "_meta": {
                    "title": "Load Image"
                }
            }
            
            # Create VAEEncode node
            vae_encode_id = str(max_node_id + 2)
            workflow[vae_encode_id] = {
                "inputs": {
                    "pixels": [load_image_id, 0],
                    "vae": [vae_node_id, 0] if vae_node_id else ["15", 0]
                },
                "class_type": "VAEEncode",
                "_meta": {
                    "title": "VAE Encode"
                }
            }
            
            # Update KSampler to use the encoded image
            for ksampler_id, ksampler_data in workflow.items():
                if ksampler_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                    ksampler_inputs = ksampler_data.get("inputs", {})
                    if "latent_image" in ksampler_inputs:
                        # Replace the reference to EmptySD3LatentImage with VAEEncode
                        latent_ref = ksampler_inputs["latent_image"]
                        if isinstance(latent_ref, list) and len(latent_ref) > 0:
                            if str(latent_ref[0]) == str(node_id):
                                ksampler_inputs["latent_image"] = [vae_encode_id, 0]
            
            # Remove the EmptySD3LatentImage node
            del workflow[node_id]
            break
    
    return workflow


def update_loadimageoutput_nodes(workflow: Dict[str, Any], source_image_filename: str) -> Dict[str, Any]:
    # Handle ComfyUI format (nodes array)
    if isinstance(workflow, dict) and "nodes" in workflow:
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
                
            if node.get("type") == "LoadImageOutput":
                # Update the image reference in the node via widgets_values
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) >= 1:
                    widgets[0] = source_image_filename
                    node["widgets_values"] = widgets
                    logger.debug(f"Updated LoadImageOutput node to use: {source_image_filename}")
    
    return workflow
