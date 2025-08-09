import json
import os
import httpx
import uuid
from typing import Dict, Any
from .utils import generate_seed
from .model_mapper import get_workflow_file
from .config import Settings


async def download_image(url: str, filename: str) -> str:
    """Download image from URL and save it to ComfyUI input directory"""
    # ComfyUI input directory is typically ComfyUI/input/
    input_dir = "/tmp/comfyui_inputs"  # Adjust this path as needed
    os.makedirs(input_dir, exist_ok=True)
    
    filepath = os.path.join(input_dir, filename)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
    
    return filename


def load_workflow_file(workflow_filename: str) -> Dict[str, Any]:
    """Load a workflow JSON file from the workflows directory"""
    workflow_path = os.path.join(Settings.WORKFLOW_DIR, workflow_filename)
    
    if not os.path.exists(workflow_path):
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")
    
    with open(workflow_path, 'r') as f:
        return json.load(f)


async def process_workflow(workflow: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """Process a workflow by replacing placeholders with job parameters"""
    payload = job.get("payload", {})
    seed = generate_seed(payload.get("seed"))
    
    # Make a deep copy to avoid modifying the original
    processed_workflow = json.loads(json.dumps(workflow))
    
    # Handle source image for img2img workflows
    source_image_filename = None
    if job.get("r2_upload") and job.get("source_processing") == "img2img":
        # Generate unique filename
        image_ext = "png"  # Default, could be improved to detect from URL
        source_image_filename = f"horde_input_{job.get('id', 'unknown')}_{uuid.uuid4().hex[:8]}.{image_ext}"
        
        try:
            await download_image(job["r2_upload"], source_image_filename)
            print(f"Downloaded source image: {source_image_filename}")
        except Exception as e:
            print(f"Failed to download source image: {e}")
            source_image_filename = None
    
    # Process each node in the workflow
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
        
        # Handle KSampler nodes
        elif class_type in ["KSampler", "KSamplerAdvanced"]:
            if "seed" in inputs or "noise_seed" in inputs:
                if "seed" in inputs:
                    inputs["seed"] = seed
                if "noise_seed" in inputs:
                    inputs["noise_seed"] = seed
            if "steps" in inputs:
                inputs["steps"] = payload.get("ddim_steps", payload.get("steps", inputs.get("steps", 6)))
            if "cfg" in inputs:
                inputs["cfg"] = payload.get("cfg_scale", inputs.get("cfg", 1.0))
            if "sampler_name" in inputs:
                sampler = payload.get("sampler_name", "euler").replace("k_", "")
                inputs["sampler_name"] = sampler
        
        # Handle text encoding nodes
        elif class_type == "CLIPTextEncode":
            if "text" in inputs:
                current_text = inputs["text"]
                # Replace with positive prompt if it's empty or a placeholder
                if current_text == "" or "POSITIVE_PROMPT_PLACEHOLDER" in current_text:
                    inputs["text"] = payload.get("prompt", "")
                # Replace negative prompt placeholder
                elif "NEGATIVE_PROMPT_PLACEHOLDER" in current_text:
                    inputs["text"] = payload.get("negative_prompt", current_text)
        
        # Handle WanImageToVideo nodes for dimensions
        elif class_type == "WanImageToVideo":
            if "width" in inputs:
                inputs["width"] = payload.get("width", inputs.get("width", 832))
            if "height" in inputs:
                inputs["height"] = payload.get("height", inputs.get("height", 832))
        
        # Handle ImageResize+ nodes
        elif class_type == "ImageResize+":
            if "width" in inputs:
                inputs["width"] = payload.get("width", inputs.get("width", 832))
            if "height" in inputs:
                inputs["height"] = payload.get("height", inputs.get("height", 832))
        
        # Handle video output nodes
        elif class_type in ["VHS_VideoCombine", "CreateVideo"]:
            if "filename_prefix" in inputs:
                job_id = job.get("id", "unknown")
                inputs["filename_prefix"] = f"horde_{job_id}"
        
        # Handle save image nodes
        elif class_type == "SaveImage":
            if "filename_prefix" in inputs:
                job_id = job.get("id", "unknown")
                inputs["filename_prefix"] = f"horde_{job_id}"
    
    return processed_workflow


async def build_workflow(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build a workflow by loading the appropriate external workflow file"""
    model_name = job.get("model", "")
    source_processing = job.get("source_processing", "txt2img")
    
    # Choose workflow based on job type and model
    if source_processing == "img2img" and job.get("r2_upload"):
        # Use image-to-video workflow for img2img jobs
        if "flux" in model_name.lower() or "krea" in model_name.lower():
            workflow_filename = "fast_image_to_video_wan22_14B.json"
        else:
            workflow_filename = "Dreamshaper.json"
    else:
        # Use the mapped workflow for text-to-image/text-to-video jobs
        workflow_filename = get_workflow_file(model_name)
    
    print(f"Loading workflow: {workflow_filename} for model: {model_name} (type: {source_processing})")
    
    try:
        workflow = load_workflow_file(workflow_filename)
        return await process_workflow(workflow, job)
    except Exception as e:
        print(f"Error loading workflow {workflow_filename}: {e}")
        # Fallback to default workflow
        try:
            fallback_workflow = load_workflow_file("Dreamshaper.json")
            return await process_workflow(fallback_workflow, job)
        except Exception as fallback_error:
            print(f"Error loading fallback workflow: {fallback_error}")
            raise RuntimeError(f"Failed to load any workflow: {e}")