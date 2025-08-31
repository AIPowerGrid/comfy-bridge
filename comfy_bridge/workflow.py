import json
import os
import httpx
import uuid
from typing import Dict, Any
from .utils import generate_seed
from .model_mapper import get_workflow_file
from .config import Settings


async def download_image(url: str, filename: str) -> str:
    """Download image from URL and upload it to ComfyUI via API"""
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

    print(f"Downloaded and uploaded image: {filename}")
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
    
    # Debug logging
    print(f"Job payload: {payload}")
    print(f"Job prompt: {payload.get('prompt')}")
    print(f"Job negative_prompt: {payload.get('negative_prompt')}")

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
                    node["widgets_values"] = widgets

            # Handle text encoding nodes - properly handle positive vs negative prompts
            elif class_type == "CLIPTextEncode":
                # In native format, prompt text is in widgets_values[0]. Use node title to infer pos/neg.
                title = node.get("title", "") or ""
                if isinstance(widgets, list) and len(widgets) >= 1:
                    if "negative" in title.lower():
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            widgets[0] = neg
                            print(f"Updated negative prompt: {neg}")
                    elif "positive" in title.lower():
                        # This is a positive prompt node
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos:
                            widgets[0] = pos
                            print(f"Updated positive prompt: {pos}")
                    else:
                        # If title doesn't specify, check if we have a prompt and this looks like a positive node
                        # (most CLIPTextEncode nodes are positive unless explicitly marked negative)
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos and not payload.get("negative_prompt"):
                            widgets[0] = pos
                            print(f"Updated unspecified prompt node with positive: {pos}")
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
                length = payload.get("video_length", payload.get("length", 81))  # Default to 81 if not specified
                if isinstance(widgets, list):
                    if w and len(widgets) >= 1:
                        widgets[0] = w
                    if h and len(widgets) >= 2:
                        widgets[1] = h
                    if len(widgets) >= 3:
                        widgets[2] = length
                    node["widgets_values"] = widgets
                print(f"Updated video parameters: width={w}, height={h}, length={length}")

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
                    print(f"Updated CreateVideo node fps to {fps}")

            # Handle LoadImageOutput nodes for source images
            elif class_type == "LoadImageOutput":
                if source_image_filename:
                    if isinstance(widgets, list) and len(widgets) >= 1:
                        widgets[0] = source_image_filename
                        node["widgets_values"] = widgets
                        print(f"Updated LoadImageOutput node {node.get('id')} to use: {source_image_filename}")
                    else:
                        node["widgets_values"] = [source_image_filename]
                        print(f"Created widgets_values for LoadImageOutput node {node.get('id')}: {source_image_filename}")

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
                                    print(f"Node {node_id} identified as negative prompt (connected to KSampler {ks_id} negative input)")
                                    break
                    
                    # If not negative, check if it's connected to positive input
                    if not is_negative_prompt:
                        for ks_id, ks_data in processed_workflow.items():
                            if isinstance(ks_data, dict) and ks_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
                                ks_inputs = ks_data.get("inputs", {})
                                if "positive" in ks_inputs:
                                    pos_ref = ks_inputs["positive"]
                                    if isinstance(pos_ref, list) and len(pos_ref) > 0 and str(pos_ref[0]) == str(node_id):
                                        is_positive_prompt = True
                                        print(f"Node {node_id} identified as positive prompt (connected to KSampler {ks_id} positive input)")
                                        break
                    
                    # Now handle the prompt based on connection type
                    if is_negative_prompt:
                        neg = payload.get("negative_prompt")
                        if isinstance(neg, str) and neg:
                            # Grid provided negative prompt - use it
                            inputs["text"] = neg
                            print(f"Updated negative prompt in API format: {neg}")
                        else:
                            # No Grid negative prompt - keep workflow default
                            print(f"Keeping workflow default negative prompt: {inputs['text']}")
                    elif is_positive_prompt:
                        # This is a positive prompt node
                        pos = payload.get("prompt")
                        if isinstance(pos, str) and pos:
                            inputs["text"] = pos
                            print(f"Updated positive prompt in API format: {pos}")
                    else:
                        # Fallback: use _meta title if connection analysis failed
                        meta = node_data.get("_meta", {})
                        title = meta.get("title", "").lower()
                        
                        if "negative" in title:
                            neg = payload.get("negative_prompt")
                            if isinstance(neg, str) and neg:
                                inputs["text"] = neg
                                print(f"Updated negative prompt by title fallback: {neg}")
                            else:
                                print(f"Keeping workflow default negative prompt by title fallback: {inputs['text']}")
                        else:
                            # Assume positive for any other CLIPTextEncode nodes
                            pos = payload.get("prompt")
                            if isinstance(pos, str) and pos:
                                inputs["text"] = pos
                                print(f"Updated unspecified prompt in API format: {pos}")

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
                    inputs["length"] = payload.get("video_length", payload.get("length", 81))  # Default to 81 frames if not specified
                # Check for fps in the CreateVideo node
                if "fps" in inputs and payload.get("fps"):
                    inputs["fps"] = payload.get("fps")
                print(f"Updated EmptyHunyuanLatentVideo node with dimensions: {inputs.get('width')}x{inputs.get('height')}, length: {inputs.get('length')}")

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
                    print(f"Updated CreateVideo node fps to {inputs['fps']}")

            # Handle LoadImageOutput nodes for source images
            elif class_type == "LoadImageOutput":
                if source_image_filename and "image" in inputs:
                    inputs["image"] = source_image_filename
                    print(f"Updated LoadImageOutput node {node_id} to use: {source_image_filename}")

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
                # Update the image reference in the node via widgets_values
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list) and len(widgets) >= 1:
                    widgets[0] = source_image_filename
                    node["widgets_values"] = widgets
                    print(f"Updated LoadImageOutput node to use: {source_image_filename}")
    
    return workflow
