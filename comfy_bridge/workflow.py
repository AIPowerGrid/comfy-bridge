import json
import os
import httpx
import uuid
import logging
from typing import Dict, Any, Optional
from .utils import generate_seed
from .model_mapper import get_workflow_file
from .config import Settings

logger = logging.getLogger(__name__)


def detect_workflow_model_type(workflow: Dict[str, Any]) -> str:
    """Detect the model type (flux, wanvideo, sdxl, etc.) from workflow nodes"""
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue
        
        class_type = node_data.get("class_type", "")
        
        # WanVideo workflows use WanVideo-specific nodes
        if class_type in ["WanVideoModelLoader", "WanVideoVAELoader", "WanVideoSampler", 
                          "WanVideoTextEmbedBridge", "WanVideoEmptyEmbeds", "WanVideoDecode"]:
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


async def validate_and_fix_model_filenames(
    workflow: Dict[str, Any], 
    available_models: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and fix model filenames in workflow to match available models.
    
    Only replaces models with compatible model types (e.g., Flux with Flux, WanVideo with WanVideo).
    Fails if no compatible models are available.
    """
    fixed_workflow = json.loads(json.dumps(workflow))  # Deep copy
    fixes_applied = []
    model_type = detect_workflow_model_type(workflow)
    
    logger.info(f"Detected workflow model type: {model_type}")
    
    if model_type == "unknown":
        logger.warning("Could not detect workflow model type - proceeding with validation anyway")
    
    for node_id, node_data in fixed_workflow.items():
        if not isinstance(node_data, dict):
            continue
            
        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})
        
        # Fix DualCLIPLoader (Flux models)
        if class_type == "DualCLIPLoader":
            if model_type != "flux":
                logger.warning(f"Node {node_id}: DualCLIPLoader found but workflow type is {model_type} - may be incompatible")
            
            dual_clip_models = available_models.get("DualCLIPLoader", {})
            clip1_options = dual_clip_models.get("clip_name1", [])
            clip2_options = dual_clip_models.get("clip_name2", [])
            
            # Filter to compatible models only
            if model_type == "flux":
                clip1_options = [m for m in clip1_options if is_model_compatible(m, "flux")]
                clip2_options = [m for m in clip2_options if is_model_compatible(m, "flux")]
            
            # Check clip_name1 - must check if input exists FIRST, then validate options
            if "clip_name1" in inputs:
                current_clip1 = inputs.get("clip_name1")
                if not clip1_options:
                    error_msg = (
                        f"Node {node_id}: No compatible Flux CLIP models available for DualCLIPLoader clip_name1. "
                        f"Workflow requires '{current_clip1}' but no Flux-compatible models are installed. "
                        f"Available models are for different model types (WanVideo, etc.)"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
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
                    error_msg = (
                        f"Node {node_id}: No compatible Flux CLIP models available for DualCLIPLoader clip_name2. "
                        f"Workflow requires '{current_clip2}' but no Flux-compatible models are installed. "
                        f"Available models are for different model types (WanVideo, etc.)"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
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
            
            unet_options = available_models.get("UNETLoader", [])
            
            # Filter to compatible models only
            if model_type == "flux":
                unet_options = [m for m in unet_options if is_model_compatible(m, "flux")]
            
            if "unet_name" in inputs:
                current_unet = inputs.get("unet_name")
                if not unet_options:
                    error_msg = (
                        f"Node {node_id}: No compatible Flux UNET models available. "
                        f"Workflow requires '{current_unet}' but no Flux-compatible models are installed. "
                        f"Available models are for different model types (WanVideo, etc.)"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                elif current_unet not in unet_options:
                    new_unet = unet_options[0]
                    logger.warning(
                        f"Node {node_id}: Replacing UNETLoader unet_name '{current_unet}' "
                        f"with '{new_unet}' (not in available models: {unet_options})"
                    )
                    inputs["unet_name"] = new_unet
                    fixes_applied.append(f"Node {node_id} unet_name: {current_unet} -> {new_unet}")
        
        # Fix VAELoader (Flux models)
        elif class_type == "VAELoader":
            if model_type != "flux":
                logger.warning(f"Node {node_id}: VAELoader found but workflow type is {model_type} - may be incompatible")
            
            vae_options = available_models.get("VAELoader", [])
            
            # Filter to compatible models only
            if model_type == "flux":
                vae_options = [m for m in vae_options if is_model_compatible(m, "flux")]
            
            if "vae_name" in inputs:
                current_vae = inputs.get("vae_name")
                if not vae_options:
                    error_msg = (
                        f"Node {node_id}: No compatible Flux VAE models available. "
                        f"Workflow requires '{current_vae}' but no Flux-compatible models are installed. "
                        f"Available models are for different model types (WanVideo, etc.)"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                elif current_vae not in vae_options:
                    new_vae = vae_options[0]
                    logger.warning(
                        f"Node {node_id}: Replacing VAELoader vae_name '{current_vae}' "
                        f"with '{new_vae}' (not in available models: {vae_options})"
                    )
                    inputs["vae_name"] = new_vae
                    fixes_applied.append(f"Node {node_id} vae_name: {current_vae} -> {new_vae}")
    
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

    with open(workflow_path, "r") as f:
        data = json.load(f)
        
    # Validate workflow has actual model file names, not placeholders
    _validate_workflow_model_names(data, workflow_filename)
    
    # Return a deep copy so callers can safely mutate without caching stale fields
    return json.loads(json.dumps(data))


def _validate_workflow_model_names(workflow: Dict[str, Any], filename: str) -> None:
    placeholders = ["checkpoint_name.safetensors", "model.safetensors", "checkpoint.safetensors"]
    model_fields = {
        "CheckpointLoaderSimple": "ckpt_name",
        "UNETLoader": "unet_name",
        "CLIPLoader": "clip_name",
        "VAELoader": "vae_name"
    }
    
    if isinstance(workflow, dict) and "nodes" in workflow:
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            class_type = node.get("type", "")
            if class_type in model_fields:
                model_name = node.get("inputs", {}).get(model_fields[class_type], "")
                if model_name in placeholders:
                    logger.warning(f"Workflow {filename} has placeholder '{model_name}' - export from ComfyUI with actual model files")
    else:
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            class_type = node_data.get("class_type", "")
            if class_type in model_fields:
                model_name = node_data.get("inputs", {}).get(model_fields[class_type], "")
                if model_name in placeholders:
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
    processed_workflow = json.loads(json.dumps(workflow))

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
    payload_steps = payload.get("ddim_steps") or payload.get("steps")
    payload_cfg = payload.get("cfg_scale") or payload.get("cfg") or payload.get("guidance")
    payload_sampler_raw = payload.get("sampler_name") or payload.get("sampler")
    payload_sampler = map_sampler_name(payload_sampler_raw) if payload_sampler_raw else None
    payload_scheduler = payload.get("scheduler")
    if not payload_scheduler and payload.get("karras") is not None:
        payload_scheduler = "karras" if payload.get("karras") else "normal"
    payload_denoise = payload.get("denoising_strength") or payload.get("denoise")

    def _apply_ksampler_dict(inputs: Dict[str, Any]) -> Dict[str, Any]:
        if payload_steps is not None and "steps" in inputs:
            inputs["steps"] = payload_steps
        if payload_cfg is not None:
            if "cfg" in inputs:
                inputs["cfg"] = payload_cfg
            elif "cfg_scale" in inputs:
                inputs["cfg_scale"] = payload_cfg
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
        if payload_steps is not None and len(widgets) >= 2:
            widgets[1] = payload_steps
        if payload_cfg is not None and len(widgets) >= 3:
            widgets[2] = payload_cfg
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
                    
                    # If not negative, check if it's connected to positive input
                    if not is_negative_prompt:
                        for ks_id, ks_data in processed_workflow.items():
                            if isinstance(ks_data, dict) and ks_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                                ks_inputs = ks_data.get("inputs", {})
                                if "positive" in ks_inputs:
                                    pos_ref = ks_inputs["positive"]
                                    logger.info(f"Checking KSampler {ks_id}: positive ref={pos_ref}, node_id={node_id}, match={isinstance(pos_ref, list) and len(pos_ref) > 0 and str(pos_ref[0]) == str(node_id)}")
                                    if isinstance(pos_ref, list) and len(pos_ref) > 0 and str(pos_ref[0]) == str(node_id):
                                        is_positive_prompt = True
                                        logger.info(f"Node {node_id} identified as positive prompt (connected to KSampler {ks_id} positive input)")
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

    return processed_workflow


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
