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

        with open(filepath, "wb") as f:
            f.write(response.content)

    return filename


def load_workflow_file(workflow_filename: str) -> Dict[str, Any]:
    """Load a workflow JSON file from the workflows directory"""
    workflow_path = os.path.join(Settings.WORKFLOW_DIR, workflow_filename)

    if not os.path.exists(workflow_path):
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    with open(workflow_path, "r") as f:
        return json.load(f)


async def process_workflow(
    workflow: Dict[str, Any], job: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a workflow by replacing only prompt, seed, and resolution"""
    payload = job.get("payload", {})
    seed = generate_seed(payload.get("seed"))

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
            print(f"Downloaded source image: {source_image_filename}")
        except Exception as e:
            print(f"Failed to download source image: {e}")
            source_image_filename = None
    else:
        print(f"Skipping image download - this is a text-to-image job")

    # Update LoadImageOutput nodes for img2img jobs
    if job.get("source_processing") == "img2img" and source_image_filename:
        processed_workflow = update_loadimageoutput_nodes(processed_workflow, source_image_filename)

    # Process each node in the workflow
    # Handle ComfyUI format (nodes array)
    if isinstance(processed_workflow, dict) and "nodes" in processed_workflow:
        nodes = processed_workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue

            inputs = node.get("inputs", {})
            class_type = node.get("type")  # ComfyUI uses "type" instead of "class_type"

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
                # Keep all other KSampler settings exactly as they are

            # Handle text encoding nodes - properly handle positive vs negative prompts
            elif class_type == "CLIPTextEncode":
                if "text" in inputs:
                    # Find which input this CLIPTextEncode connects to in the KSampler
                    is_positive_prompt = False
                    is_negative_prompt = False
                    
                    # Check all KSampler nodes to see which input this CLIPTextEncode connects to
                    for ksampler_node in nodes:
                        if ksampler_node.get("type") in ["KSampler", "KSamplerAdvanced"]:
                            ksampler_inputs = ksampler_node.get("inputs", {})
                            # Check if this CLIPTextEncode connects to positive input (robust to str/int ids)
                            pos_ref = ksampler_inputs.get("positive")
                            neg_ref = ksampler_inputs.get("negative")
                            try:
                                if isinstance(pos_ref, list) and pos_ref:
                                    if str(pos_ref[0]) == str(node.get("id")):
                                        is_positive_prompt = True
                                if isinstance(neg_ref, list) and neg_ref:
                                    if str(neg_ref[0]) == str(node.get("id")):
                                        is_negative_prompt = True
                            except Exception:
                                pass
                    
                    # Only replace positive prompts with job prompt
                    if is_positive_prompt and payload.get("prompt"):
                        inputs["text"] = payload.get("prompt")
                    # Replace negative prompt only if provided in payload; otherwise keep workflow default
                    elif is_negative_prompt:
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            inputs["text"] = neg
                    # For any other CLIPTextEncode nodes, keep original text
                    else:
                        pass

            # Handle latent image nodes - only update dimensions if specified
            elif class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                if "width" in inputs and payload.get("width"):
                    inputs["width"] = payload.get("width")
                if "height" in inputs and payload.get("height"):
                    inputs["height"] = payload.get("height")

            # Handle save image nodes - update filename prefix for job tracking
            elif class_type == "SaveImage":
                if "filename_prefix" in inputs:
                    job_id = job.get("id", "unknown")
                    inputs["filename_prefix"] = f"horde_{job_id}"

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
                # Keep all other KSampler settings exactly as they are

            # Handle text encoding nodes - properly handle positive vs negative prompts
            elif class_type == "CLIPTextEncode":
                if "text" in inputs:
                    # Find which input this CLIPTextEncode connects to in the KSampler
                    is_positive_prompt = False
                    is_negative_prompt = False
                    
                    # Check all KSampler nodes to see which input this CLIPTextEncode connects to
                    for ksampler_id, ksampler_data in processed_workflow.items():
                        if ksampler_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                            ksampler_inputs = ksampler_data.get("inputs", {})
                            # Check if this CLIPTextEncode connects to positive input (robust to str/int ids)
                            pos_ref = ksampler_inputs.get("positive")
                            neg_ref = ksampler_inputs.get("negative")
                            try:
                                if isinstance(pos_ref, list) and pos_ref:
                                    if str(pos_ref[0]) == str(node_id):
                                        is_positive_prompt = True
                                if isinstance(neg_ref, list) and neg_ref:
                                    if str(neg_ref[0]) == str(node_id):
                                        is_negative_prompt = True
                            except Exception:
                                pass
                    
                    # Only replace positive prompts with job prompt
                    if is_positive_prompt and payload.get("prompt"):
                        inputs["text"] = payload.get("prompt")
                    # Replace negative prompt only if provided in payload; otherwise keep workflow default
                    elif is_negative_prompt:
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            inputs["text"] = neg
                    # For any other CLIPTextEncode nodes, keep original text
                    else:
                        pass

            # Handle latent image nodes - only update dimensions if specified
            elif class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                if "width" in inputs and payload.get("width"):
                    inputs["width"] = payload.get("width")
                if "height" in inputs and payload.get("height"):
                    inputs["height"] = payload.get("height")

            # Handle save image nodes - update filename prefix for job tracking
            elif class_type == "SaveImage":
                if "filename_prefix" in inputs:
                    job_id = job.get("id", "unknown")
                    inputs["filename_prefix"] = f"horde_{job_id}"

    return processed_workflow


async def build_workflow(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build a workflow by loading the appropriate external workflow file"""
    model_name = job.get("model", "")
    source_processing = job.get("source_processing", "txt2img")

    # Use the mapped workflow for all jobs (the mapper handles the logic)
    workflow_filename = get_workflow_file(model_name)
    
    # Validate that we have a proper workflow mapping
    if not workflow_filename:
        error_msg = f"No workflow mapping found for model: {model_name}"
        if Settings.WORKFLOW_FILE:
            error_msg += f" (Available workflows: {Settings.WORKFLOW_FILE})"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    print(f"Loading workflow: {workflow_filename} for model: {model_name} (type: {source_processing})")
    
    try:
        workflow = load_workflow_file(workflow_filename)
        return await process_workflow(workflow, job)
    except Exception as e:
        print(f"Error loading workflow {workflow_filename}: {e}")
        raise RuntimeError(f"Failed to load workflow {workflow_filename} for model {model_name}: {e}")


def convert_to_img2img(workflow: Dict[str, Any], source_image_filename: str) -> Dict[str, Any]:
    """Convert a text-to-image workflow to img2img by replacing EmptySD3LatentImage with LoadImage + VAEEncode"""
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
    """Update LoadImageOutput nodes in ComfyUI format workflows to reference the source image"""
    # Handle ComfyUI format (nodes array)
    if isinstance(workflow, dict) and "nodes" in workflow:
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
                
            if node.get("type") == "LoadImageOutput":
                # Update the image reference in the node
                if "inputs" not in node:
                    node["inputs"] = {}
                node["inputs"]["image"] = source_image_filename
                print(f"Updated LoadImageOutput node to use: {source_image_filename}")
    
    return workflow
