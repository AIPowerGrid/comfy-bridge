"""ComfyUI bridge for AI Power Grid image worker.

This module provides a bridge between the AI Power Grid network and a local ComfyUI installation.
It allows a local ComfyUI installation to act as an AI Power Grid image worker by:
1. Connecting to the AI Power Grid API
2. Receiving image generation jobs
3. Converting them to ComfyUI workflows
4. Submitting them to a local ComfyUI instance
5. Returning the results to the AI Power Grid
"""

import asyncio
import base64
import json
import os
import time
import httpx
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

import requests
import PIL.Image
from dotenv import load_dotenv
import aiohttp

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("comfy_bridge")

# Import our model mapper
from model_mapper import initialize_model_mapper, get_horde_models, map_model_name

# In a real implementation, we would properly import from the Horde SDK
# For now, we'll create dummy classes to represent the API models
class DummyJobPopResponse:
    """Dummy class to represent a job from the AI Power Grid."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.model = kwargs.get("model", "")
        self.kudos = kwargs.get("kudos", 0)
        
        # Create a payload object
        class Payload:
            def __init__(self, payload_data):
                self.prompt = payload_data.get("prompt", "")
                self.negative_prompt = payload_data.get("negative_prompt", "")
                self.steps = payload_data.get("steps", 30)
                self.cfg_scale = payload_data.get("cfg_scale", 7.0)
                self.width = payload_data.get("width", 512)
                self.height = payload_data.get("height", 512)
                self.seed = payload_data.get("seed", 0)
                self.sampler = payload_data.get("sampler_name", "euler_ancestral")
                self.use_nsfw_censor = payload_data.get("use_nsfw_censor", False)
        
        self.payload = Payload(kwargs.get("payload", {}))

class ComfyUIBridge:
    """Bridge between AI Power Grid and a local ComfyUI installation."""
    
    def __init__(self, worker_name, api_key, base_url=None, comfy_url=None, nsfw=False, threads=1, max_pixels=1048576, workflow_dir=None, workflow_file=None, grid_model=None):
        """Initialize the bridge."""
        self.worker_name = worker_name
        self.api_key = api_key
        self.base_url = base_url or "https://api.aipowergrid.io/api"
        self.comfy_url = comfy_url or "http://127.0.0.1:8000"
        self.nsfw = nsfw
        self.threads = threads
        self.max_pixels = max_pixels
        self.session = None
        self.logger = logging.getLogger(__name__)
        
        # Set up models - if grid_model is specified, use only that model
        self.grid_model = grid_model
        if self.grid_model:
            self.models = [self.grid_model]
            logger.info(f"Using specified grid model: {self.grid_model}")
        else:
            self.models = ["stable_diffusion"]  # Default to stable_diffusion model
            
        load_dotenv()
        self.headers = {
            "apikey": self.api_key,
            "Client-Agent": "comfyui-bridge:0.1.0",
            "Accept": "application/json"
        }
        self.comfy_client = httpx.AsyncClient(base_url=self.comfy_url, timeout=300)
        
        # Track running jobs
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        
        # Track worker status
        self.running = False
        self.total_kudos = 0
        self.jobs_completed = 0
        
        # Workflows directory 
        self.workflow_dir = workflow_dir or os.path.join(os.getcwd(), "workflows")
        
        # Active workflow file
        self.workflow_file = workflow_file
        
        logger.info(f"Initialized bridge with worker name: {self.worker_name}")
        logger.info(f"Using API URL: {self.base_url}")
        logger.info(f"Using ComfyUI URL: {self.comfy_url}")
        logger.info(f"NSFW allowed: {self.nsfw}")
        logger.info(f"Workflows directory: {self.workflow_dir}")
        logger.info(f"Advertised models: {self.models}")
        if self.workflow_file:
            logger.info(f"Using workflow file: {self.workflow_file}")
        
        # Set up the Horde API client
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Load the workflow if provided
        self.workflow_template = None
        if self.workflow_file:
            self._load_workflow_template()
    
    def _load_workflow_template(self):
        """Load the workflow template from the specified file."""
        if not self.workflow_file:
            logger.warning("No workflow file specified")
            return
            
        workflow_path = os.path.join(self.workflow_dir, self.workflow_file)
        if not os.path.exists(workflow_path):
            logger.error(f"Workflow file not found: {workflow_path}")
            return
            
        try:
            with open(workflow_path, 'r') as f:
                raw_data = json.load(f)
                logger.info(f"Loaded workflow file from {workflow_path}")
                
                # Check if this is a full workflow export with "nodes" object
                if isinstance(raw_data, dict) and "nodes" in raw_data and isinstance(raw_data["nodes"], dict):
                    logger.info("Detected full ComfyUI workflow export format with 'nodes' object")
                    self.workflow_template = raw_data["nodes"]
                # Check if this is a ComfyUI web interface export format with "nodes" array
                elif isinstance(raw_data, dict) and "nodes" in raw_data and isinstance(raw_data["nodes"], list):
                    logger.info("Detected ComfyUI web interface export format with 'nodes' array")
                    # Convert from array format to API format
                    nodes_dict = {}
                    for node in raw_data["nodes"]:
                        node_id = str(node.get("id", ""))
                        if not node_id:
                            continue
                            
                        # Create node structure expected by API
                        api_node = {
                            "class_type": node.get("type", ""),
                            "inputs": {}
                        }
                        
                        # Convert inputs
                        if "inputs" in node and isinstance(node["inputs"], list):
                            for input_item in node["inputs"]:
                                input_name = input_item.get("name", "")
                                if input_name and "link" in input_item:
                                    # Find the source node and output for this link
                                    link_id = input_item["link"]
                                    for link in raw_data.get("links", []):
                                        if link[0] == link_id:  # link ID matches
                                            source_node_id = str(link[1])  # source node ID
                                            source_slot = link[2]  # source slot index
                                            api_node["inputs"][input_name] = [source_node_id, source_slot]
                                            break
                        
                        # Process special node types
                        if node.get("type") == "CLIPTextEncode":
                            # Get prompt from widgets_values
                            if "widgets_values" in node and len(node["widgets_values"]) > 0:
                                text = node["widgets_values"][0]
                                api_node["inputs"]["text"] = text
                                
                                # Check for placeholders
                                if not text or text.strip() == "":
                                    # This is likely the negative prompt node
                                    api_node["inputs"]["text"] = "NEGATIVE_PROMPT_PLACEHOLDER"
                                    logger.info(f"Set empty text to NEGATIVE_PROMPT_PLACEHOLDER for node {node_id}")
                                elif text.strip() == "a flower" or text.strip() == "photo of a flower" or text.strip() == "photo of a beautiful flower":  # Common default values
                                    # This is likely the positive prompt node 
                                    api_node["inputs"]["text"] = "POSITIVE_PROMPT_PLACEHOLDER"
                                    logger.info(f"Set default prompt to POSITIVE_PROMPT_PLACEHOLDER for node {node_id}")
                                # Keep placeholders if they are already set
                                elif "POSITIVE_PROMPT_PLACEHOLDER" in text:
                                    logger.info(f"Found existing POSITIVE_PROMPT_PLACEHOLDER in node {node_id}")
                                elif "NEGATIVE_PROMPT_PLACEHOLDER" in text:
                                    logger.info(f"Found existing NEGATIVE_PROMPT_PLACEHOLDER in node {node_id}")
                        
                        elif node.get("type") == "KSampler":
                            # Get sampling parameters from widgets_values
                            if "widgets_values" in node and len(node["widgets_values"]) >= 6:
                                api_node["inputs"]["seed"] = node["widgets_values"][0]
                                api_node["inputs"]["steps"] = node["widgets_values"][1]
                                api_node["inputs"]["cfg"] = node["widgets_values"][2]
                                api_node["inputs"]["sampler_name"] = node["widgets_values"][3]
                                api_node["inputs"]["scheduler"] = node["widgets_values"][4]
                                api_node["inputs"]["denoise"] = node["widgets_values"][5]
                        
                        elif node.get("type") == "EmptyLatentImage":
                            # Get dimensions from widgets_values
                            if "widgets_values" in node and len(node["widgets_values"]) >= 3:
                                api_node["inputs"]["width"] = node["widgets_values"][0]
                                api_node["inputs"]["height"] = node["widgets_values"][1]
                                api_node["inputs"]["batch_size"] = node["widgets_values"][2]
                        
                        elif node.get("type") == "SaveImage":
                            # Get filename prefix
                            if "widgets_values" in node and len(node["widgets_values"]) >= 1:
                                api_node["inputs"]["filename_prefix"] = node["widgets_values"][0]
                        
                        elif node.get("type") == "CheckpointLoaderSimple":
                            # Get checkpoint name
                            if "widgets_values" in node and len(node["widgets_values"]) >= 1:
                                api_node["inputs"]["ckpt_name"] = node["widgets_values"][0]
                            
                        # Add the node to our dictionary
                        nodes_dict[node_id] = api_node
                    
                    self.workflow_template = nodes_dict
                    logger.info(f"Converted {len(nodes_dict)} nodes from web interface format to API format")
                else:
                    # Assume it's already in the right format (just nodes)
                    self.workflow_template = raw_data
                
                logger.info(f"Workflow contains {len(self.workflow_template) if isinstance(self.workflow_template, dict) else 0} nodes")
                
                # Try to extract model from workflow
                model_name = None
                if isinstance(self.workflow_template, dict):
                    for node in self.workflow_template.values():
                        if isinstance(node, dict):
                            checkpoint_name = None
                            if node.get("class_type") == "CheckpointLoaderSimple" and "inputs" in node and "ckpt_name" in node["inputs"]:
                                checkpoint_name = node["inputs"]["ckpt_name"]
                            
                            if checkpoint_name:
                                if "sdxl" in checkpoint_name.lower():
                                    if "turbo" in checkpoint_name.lower() or "lightning" in checkpoint_name.lower():
                                        model_name = "sdxl_turbo"
                                    else:
                                        model_name = "sdxl"
                                elif "v1-5" in checkpoint_name.lower():
                                    model_name = "stable_diffusion_1.5"
                                elif "v2-1" in checkpoint_name.lower():
                                    model_name = "stable_diffusion_2.1"
                                elif "turbo" in checkpoint_name.lower() or "lightning" in checkpoint_name.lower():
                                    model_name = "turbovision_xl"
                
                if model_name and model_name not in self.models:
                    self.models.append(model_name)
                    logger.info(f"Added model {model_name} based on workflow checkpoint")
        except Exception as e:
            logger.error(f"Error loading workflow template: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.workflow_template = None
            
    def _load_workflow_mappings(self):
        """Legacy method for backward compatibility."""
        return {}
        
    async def initialize_models(self):
        """Initialize available models."""
        logger.info("Initializing models from workflow template...")
        
        # Ensure workflow is loaded
        if not self.workflow_template and self.workflow_file:
            self._load_workflow_template()
                
        logger.info(f"Available models: {self.models}")
                
    async def start(self):
        """Start the bridge."""
        logger.info(f"Starting ComfyUI bridge as worker: {self.worker_name}")
        logger.info(f"Connected to ComfyUI at: {self.comfy_url}")
        logger.info(f"Using AI Power Grid API at: {self.base_url}")
        
        # Initialize the aiohttp session
        self.session = aiohttp.ClientSession()
        
        # Initialize models
        await self.initialize_models()
        
        self.running = True
        
        # Register the worker
        success = await self._register_worker()
        
        if not success:
            # If registration failed, cleanup and exit
            self.running = False
            await self._cleanup()
            return
            
        try:
            # Main processing loop
            await self._main_loop()
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
        finally:
            # Ensure we unregister on exit
            logger.info("Bridge stopping, cleaning up resources...")
            self.running = False
            
            # Attempt unregistration
            try:
                if self.session and not self.session.closed:
                    unregister_success = await self._unregister_worker()
                    if unregister_success:
                        logger.info("Successfully sent offline signal to AI Power Grid")
                        logger.info("Note: The worker may still appear online in the AI Power Grid for up to 30 minutes")
                    else:
                        logger.warning("Failed to send offline signal, but continuing shutdown")
                        logger.warning("The worker will be automatically removed from the grid after a timeout period")
            except Exception as e:
                logger.error(f"Error during worker offline signaling: {e}")
                logger.warning("The worker will be automatically removed from the grid after a timeout period")
            
            # Clean up resources
            await self._cleanup()
    
    async def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources...")
        
        try:
            if self.comfy_client:
                logger.info("Closing ComfyUI client...")
                await self.comfy_client.aclose()
                self.comfy_client = None
        except Exception as e:
            logger.error(f"Error closing ComfyUI client: {e}")
            
        try:
            if self.session and not self.session.closed:
                logger.info("Closing API session...")
                await self.session.close()
                self.session = None
        except Exception as e:
            logger.error(f"Error closing API session: {e}")
            
        logger.info("Cleanup completed.")

    async def _register_worker(self):
        """Register the worker with the AI Power Grid."""
        if not self.models:
            logger.error("No models available, cannot register worker")
            return False
            
        try:
            # Set up the headers with API key
            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json",
                "Client-Agent": "ComfyUI Bridge:1.0"
            }
            
            # Define the worker data
            worker_info = {
                "name": self.worker_name,
                "info": "ComfyUI Bridge Worker",
                "max_pixels": self.max_pixels,
                "nsfw": self.nsfw,
                "models": self.models,
                "bridge_agent": "ComfyUI Bridge:1.0",
                "threads": self.threads,
                "img2img": True,
                "painting": True,
                "post_processing": True,
                "maintenance": False,
                "type": "image"
            }
            
            # Check if worker already exists by trying to pop a job
            # This is a workaround since registration methods are limited
            logger.info(f"Attempting to register worker {self.worker_name} by joining the grid...")
            
            # Use the existing self.session rather than creating a new one
            pop_url = f"{self.base_url}/v2/generate/pop"
            payload = {
                "name": self.worker_name,
                "models": self.models,
                "max_pixels": self.max_pixels,
                "nsfw": self.nsfw,
                "bridge_agent": "ComfyUI Bridge:1.0",
                "threads": self.threads,
                "require_upfront_kudos": False,
                "worker_type": "image",
                "img2img": True,
                "painting": True,
                "post_processing": True
            }
            
            async with self.session.post(pop_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if "worker_id" in response_data:
                        worker_id = response_data["worker_id"]
                        logger.info(f"Worker {self.worker_name} successfully registered with ID {worker_id}")
                        return True
                    elif "id" in response_data or "skipped" in response_data:
                        # Either we got a job or we got 'skipped', either way our worker is live
                        logger.info(f"Worker {self.worker_name} is active")
                        return True
                    else:
                        # Unexpected response
                        logger.warning(f"Unexpected response from pop endpoint: {response_data}")
                        logger.info("Continuing anyway - worker might still be functional")
                        return True
                elif response.status == 401:
                    # Auth error
                    error_text = await response.text()
                    logger.error(f"Authentication error: {error_text}")
                    logger.error("Please check your API key")
                    return False
                elif response.status == 400 or response.status == 404:
                    # Could be worker name not found or other client error
                    error_text = await response.text()
                    logger.error(f"Unable to activate worker: {error_text}")
                    if "worker not found" in error_text.lower():
                        logger.info("Try a different worker name in your .env file")
                    return False
                else:
                    # Other error
                    error_text = await response.text()
                    logger.error(f"Unexpected status {response.status}: {error_text}")
                    logger.error("Cannot determine if worker registration succeeded")
                    return False
            
        except Exception as e:
            logger.error(f"Error registering worker: {str(e)}")
            return False

    async def _unregister_worker(self):
        """
        Signal to the AI Power Grid that this worker is no longer available.
        
        Note: The AI Power Grid API doesn't provide a direct way to unregister workers.
        Instead, we send a pop request with online=false and maintenance=true to signal
        that the worker is going offline. The worker will eventually be marked as offline
        after a period of inactivity.
        """
        # If session is None, we can't unregister
        if self.session is None or self.session.closed:
            logger.warning("Session is None or closed, cannot signal worker unavailability")
            return False

        logger.info(f"Signaling worker {self.worker_name} is going offline")
            
        try:
            # Set a timeout for the request
            timeout = aiohttp.ClientTimeout(total=10)
            
            # This is the pop endpoint where we can signal our status
            pop_url = f"{self.base_url}/v2/generate/pop"
            
            # Prepare payload - indicate we're going offline
            pop_payload = {
                "name": self.worker_name,
                "models": self.models,
                "max_pixels": self.max_pixels,
                "nsfw": self.nsfw,
                "bridge_agent": "ComfyUI Bridge:1.0",
                "threads": self.threads,
                "online": False,
                "maintenance": True,
                "worker_type": "image"
            }
            
            try:
                # Only attempt once with a sufficient timeout
                async with self.session.post(
                    pop_url, 
                    headers=self.headers, 
                    json=pop_payload, 
                    timeout=timeout
                ) as response:
                    response_status = response.status
                    
                    try:
                        # Try to get response text but don't fail if we can't
                        response_text = await response.text()
                    except Exception:
                        response_text = "Could not get response text"
                    
                    if response_status == 200:
                        logger.info("Successfully sent offline signal to AI Power Grid")
                        logger.info("Note: The AI Power Grid may still show this worker as online for up to 30 minutes.")
                        logger.info("This is normal behavior - the worker will be automatically removed from the grid after a timeout period.")
                        return True
                    else:
                        logger.warning(f"Received unexpected status code when sending offline signal: {response_status} - {response_text}")
                        logger.warning("The worker will be automatically removed from the grid after a timeout period.")
                        # Still return True since we're shutting down anyway
                        return True
                
            except asyncio.TimeoutError:
                logger.warning("Timeout sending offline signal to AI Power Grid")
                # Still return True since we're shutting down anyway
                return True
            except Exception as e:
                logger.error(f"Error sending offline signal: {str(e)}")
                # Still return True to allow shutdown to continue
                return True
                
        except Exception as e:
            logger.error(f"Error in worker offline signaling: {str(e)}")
            # Still return True to allow shutdown to continue
            return True

    async def _pop_jobs(self):
        """Pop jobs from the AI Power Grid."""
        url = f"{self.base_url}/v2/generate/pop"
        payload = {
            "name": self.worker_name,
            "models": self.models,
            "max_pixels": self.max_pixels,
            "nsfw": self.nsfw,
            "bridge_agent": "ComfyUI Bridge:1.0:https://github.com/comfyanonymous/ComfyUI",
            "threads": self.threads,
            "require_upfront_kudos": False,
            "worker_type": "image",
            "allow_img2img": True,
            "allow_painting": True
        }
        try:
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if "id" in data:
                        logger.info(f"Got job {data['id']}")
                    return data
                else:
                    logger.error(f"Failed to pop jobs: {response.status} - {await response.text()}")
                    return None
        except Exception as e:
            logger.error(f"Error popping jobs: {e}")
            return None

    async def _submit_result(self, job_id: str, image_data: bytes):
        """Submit a completed job result to the AI Power Grid."""
        logger.info(f"Preparing to submit result for job {job_id}, image size: {len(image_data)} bytes")
        
        # Convert image to base64
        image_base64 = base64.b64encode(image_data).decode()
        logger.info(f"Base64 encoded image size: {len(image_base64)} characters")
        
        url = f"{self.base_url}/v2/generate/submit"
        
        # Get seed and ensure it's an integer
        seed = self.active_jobs.get(job_id, {}).get('seed', 0)
        if not isinstance(seed, int):
            try:
                seed = int(seed)
            except (ValueError, TypeError):
                seed = 0
                
        payload = {
            "id": job_id,
            "generation": image_base64,
            "state": "ok",
            "seed": seed
        }
        
        logger.info(f"Submitting to API URL: {url}")
        
        try:
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                response_status = response.status
                response_text = await response.text()
                
                if response_status == 200:
                    logger.info(f"Successfully submitted result for job {job_id}")
                    return True
                else:
                    logger.error(f"Failed to submit result: {response_status} - {response_text}")
                    return False
        except Exception as e:
            logger.error(f"Exception during result submission: {str(e)}")
            return False

    async def _submit_failure(self, job_id: str, error: str):
        """Submit a job failure to the AI Power Grid."""
        url = f"{self.base_url}/v2/generate/submit"
        
        # Get seed or default to 0
        seed = 0
        if job_id in self.active_jobs:
            seed = self.active_jobs[job_id].get('seed', 0)
        
        # Create a dummy base64 image (1x1 transparent pixel) to satisfy the API
        dummy_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        
        payload = {
            "id": job_id,
            "state": "faulted",
            "seed": seed,
            "generation": dummy_image,  # Add empty generation
            "error": error
        }
        
        try:
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Successfully submitted failure for job {job_id}")
                    return True
                else:
                    logger.error(f"Failed to submit failure: {response.status} {await response.text()}")
                    return False
        except Exception as e:
            logger.error(f"Error submitting failure: {e}")
            return False

    async def _main_loop(self):
        """Main loop for the bridge"""
        # The session is already initialized in start() method, don't create a new one here
        if not await self._register_worker():
            return

        try:
            while self.running:
                jobs = await self._pop_jobs()
                if jobs and not jobs.get("skipped", {}):
                    # Process jobs here
                    logger.info(f"Got jobs: {jobs}")
                    
                    # Check if 'id' exists in jobs (it's a single job)
                    if 'id' in jobs:
                        try:
                            # Create a dummy job object from the JSON
                            job = DummyJobPopResponse(**jobs)
                            await self._process_job(job)
                        except Exception as e:
                            logger.error(f"Error processing job: {e}")
                    else:
                        logger.warning("Received job data in unexpected format")
                else:
                    # Check if we should shutdown
                    if not self.running:
                        logger.info("Shutdown requested, stopping main loop")
                        break
                    
                    # Wait with periodic checks for shutdown
                    for _ in range(10):  # 10 x 0.1s = 1s total wait time
                        if not self.running:
                            logger.info("Shutdown requested during wait, stopping main loop")
                            break
                        await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Shutting down main loop...")
            # This is expected during shutdown, don't treat as error
            self.running = False
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            self.running = False
        finally:
            # Don't call unregister here, it will be called by the start() method
            pass

    async def _process_job(self, job: DummyJobPopResponse):
        """Process a single job.
        
        Args:
            job: Job information from the AI Power Grid
        """
        job_id = job.id
        logger.info(f"Processing job {job_id} with model {job.model}")
        
        try:
            # Store job information in active_jobs dictionary
            self.active_jobs[job_id] = {
                'seed': int(job.payload.seed) if job.payload.seed else 0,
                'model': job.model,
                'kudos': job.kudos or 0
            }
            
            # Convert AI Power Grid job to ComfyUI workflow
            workflow = self._convert_job_to_workflow(job)
            
            # Submit workflow to ComfyUI
            prompt_id = await self._submit_workflow(workflow)
            
            # Wait for the image generation to complete
            result = await self._wait_for_generation(prompt_id)
            
            # Get the generated image
            image_data = await self._get_generated_image(result)
            
            # Submit the result back to the AI Power Grid
            await self._submit_result(job_id, image_data)
            
            # Track stats
            self.jobs_completed += 1
            self.total_kudos += job.kudos or 0
            
            logger.info(f"Job {job_id} completed successfully (earned {job.kudos} kudos)")
            
            # Clean up active job
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            # Inform the Power Grid about the failure
            await self._submit_failure(job_id, str(e))
            
            # Clean up active job
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    def _convert_job_to_workflow(self, job: DummyJobPopResponse) -> Dict[str, Any]:
        """Convert an AI Power Grid job to a ComfyUI workflow using a workflow template file."""
        # If we have a loaded workflow template, use it
        if self.workflow_template:
            logger.info(f"Using loaded workflow template for job with model {job.model}")
            return self._update_workflow_with_job_params(self.workflow_template, job)
        
        # Otherwise fall back to default workflow
        logger.warning(f"No workflow template loaded, falling back to default workflow for {job.model}")
        return self._create_default_workflow(job)
    
    def _update_workflow_with_job_params(self, workflow: Dict[str, Any], job: DummyJobPopResponse) -> Dict[str, Any]:
        """Update a workflow template with job-specific parameters."""
        # Make a deep copy to avoid modifying the template
        updated_workflow = json.loads(json.dumps(workflow))
        
        # Remove any non-dictionary nodes and nodes without class_type
        nodes_to_remove = []
        for node_id, node in updated_workflow.items():
            if not isinstance(node, dict):
                logger.warning(f"Skipping non-dictionary node: {node_id}")
                nodes_to_remove.append(node_id)
            elif "class_type" not in node:
                logger.warning(f"Skipping node without class_type: {node_id}")
                nodes_to_remove.append(node_id)
                
        for node_id in nodes_to_remove:
            updated_workflow.pop(node_id, None)
            
        if nodes_to_remove:
            logger.info(f"Cleaned up workflow: removed {len(nodes_to_remove)} invalid nodes")
        
        # First find the KSampler node to determine which nodes are really used for positive/negative
        ksampler_node = None
        ksampler_node_id = None
        for node_id, node in updated_workflow.items():
            if isinstance(node, dict) and node.get("class_type") == "KSampler" and "inputs" in node:
                ksampler_node = node
                ksampler_node_id = node_id
                logger.info(f"Found KSampler node: {node_id}")
                break
                
        # Find the node IDs for positive and negative prompts from KSampler connections
        positive_node_id = None
        negative_node_id = None
        
        if ksampler_node and "inputs" in ksampler_node:
            if "positive" in ksampler_node["inputs"] and isinstance(ksampler_node["inputs"]["positive"], list):
                positive_node_id = ksampler_node["inputs"]["positive"][0]
                logger.info(f"KSampler positive prompt connects to node: {positive_node_id}")
                
            if "negative" in ksampler_node["inputs"] and isinstance(ksampler_node["inputs"]["negative"], list):
                negative_node_id = ksampler_node["inputs"]["negative"][0]
                logger.info(f"KSampler negative prompt connects to node: {negative_node_id}")
        
        # Parse the prompt from the job - split at ### if present
        prompt = job.payload.prompt or ""
        negative_prompt = job.payload.negative_prompt or ""
        
        # If prompt contains ###, split it into positive and negative parts
        if "###" in prompt:
            parts = prompt.split("###", 1)
            positive_prompt = parts[0].strip()
            # If a negative prompt was already provided separately, don't override it
            if not negative_prompt and len(parts) > 1:
                negative_prompt = parts[1].strip()
            logger.info(f"Split prompt at ### delimiter: positive='{positive_prompt[:30]}...', negative='{negative_prompt[:30]}...'")
        else:
            positive_prompt = prompt
            logger.info(f"No ### delimiter found in prompt, using full prompt as positive")
        
        # ONLY update the prompt-related fields, NOT sampler or other parameters
        for node_id, node in updated_workflow.items():
            # Skip string values or non-dictionary nodes
            if not isinstance(node, dict):
                continue
                
            # Make sure inputs dict exists
            if "inputs" not in node:
                node["inputs"] = {}
            
            # Find CLIPTextEncode nodes for prompt and negative prompt based on connections
            if node.get("class_type") == "CLIPTextEncode":
                # If this is the positive prompt node
                if node_id == positive_node_id:
                    node["inputs"]["text"] = positive_prompt
                    logger.info(f"Set positive prompt in node {node_id}: {positive_prompt[:30]}...")
                    
                    # Update widgets_values too for compatibility
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        node["widgets_values"][0] = positive_prompt
                
                # If this is the negative prompt node
                elif node_id == negative_node_id:
                    node["inputs"]["text"] = negative_prompt
                    logger.info(f"Set negative prompt in node {node_id}: {negative_prompt[:30]}...")
                    
                    # Update widgets_values too for compatibility
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        node["widgets_values"][0] = negative_prompt
                
                # If connections not determined but we have placeholder text
                elif positive_node_id is None or negative_node_id is None:
                    # Fall back to placeholder method
                    if "text" in node["inputs"]:
                        if node["inputs"]["text"] == "POSITIVE_PROMPT_PLACEHOLDER":
                            node["inputs"]["text"] = positive_prompt
                            logger.info(f"Set positive prompt by placeholder in node {node_id}")
                        elif node["inputs"]["text"] == "NEGATIVE_PROMPT_PLACEHOLDER":
                            node["inputs"]["text"] = negative_prompt
                            logger.info(f"Set negative prompt by placeholder in node {node_id}")
                    
                    # Also check for placeholders in widgets_values
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        if node["widgets_values"][0] == "POSITIVE_PROMPT_PLACEHOLDER":
                            node["widgets_values"][0] = positive_prompt
                            # Also update inputs.text for API compatibility
                            node["inputs"]["text"] = positive_prompt
                            logger.info(f"Set positive prompt by placeholder in widgets_values for node {node_id}")
                        elif node["widgets_values"][0] == "NEGATIVE_PROMPT_PLACEHOLDER":
                            node["widgets_values"][0] = negative_prompt
                            # Also update inputs.text for API compatibility
                            node["inputs"]["text"] = negative_prompt
                            logger.info(f"Set negative prompt by placeholder in widgets_values for node {node_id}")
            
            # Only update SaveImage node to set filename with job ID
            elif node.get("class_type") == "SaveImage":
                node["inputs"]["filename_prefix"] = f"horde_{job.id}"
                logger.info(f"Set SaveImage filename prefix to horde_{job.id}")
                
        # Log what we're keeping from local workflow
        if ksampler_node:
            logger.info(f"Using sampler from local workflow: {ksampler_node['inputs'].get('sampler_name', 'unknown')}")
            logger.info(f"Using steps from local workflow: {ksampler_node['inputs'].get('steps', 'unknown')}")
            logger.info(f"Using CFG from local workflow: {ksampler_node['inputs'].get('cfg', 'unknown')}")
        
        # Debug output if something still seems wrong
        if not updated_workflow:
            logger.error("No valid nodes found in workflow!")
            
        return updated_workflow

    def _map_sampler(self, sampler_name: str) -> str:
        """Map AI Power Grid sampler names to ComfyUI sampler names."""
        # Comprehensive mapping of samplers between AI Power Grid and ComfyUI
        sampler_mapping = {
            # Standard mappings
            "k_dpm_2_ancestral": "dpm_2_ancestral",
            "k_dpm_2": "dpm_2",
            "k_euler_ancestral": "euler_ancestral",
            "k_euler": "euler",
            "k_heun": "heun",
            "k_lms": "lms",
            "k_dpmpp_2s_ancestral": "dpmpp_2s_ancestral",
            
            # Additional mappings for common samplers
            "k_dpmpp_2m": "dpmpp_2m",  # May need to be mapped to an available alternative
            "k_dpmpp_sde": "dpmpp_sde",
            "ddim": "ddim",
            "plms": "plms",
            "unipc": "unipc"
        }
        
        # If the sampler isn't in our mapping, try to fix common variants
        if sampler_name not in sampler_mapping:
            # Convert to lowercase and remove any 'k_' prefix if present
            normalized_name = sampler_name.lower()
            if normalized_name.startswith("k_"):
                normalized_name = normalized_name[2:]
                
            logger.info(f"Trying to map unknown sampler '{sampler_name}' → '{normalized_name}'")
            
            # Check if the normalized name is a known ComfyUI sampler
            return normalized_name
        
        # Check if we should use a fallback for specific problematic samplers
        if sampler_name == "k_dpmpp_2m":
            # These are good fallbacks that most ComfyUI installations support
            fallbacks = ["euler_ancestral", "euler", "dpm_2_ancestral", "dpmpp_2s_ancestral"]
            logger.warning(f"Sampler '{sampler_name}' may not be supported, trying fallbacks: {fallbacks[0]}")
            return fallbacks[0]
            
        # Return the mapped sampler name or the original as fallback
        mapped_name = sampler_mapping.get(sampler_name, sampler_name)
        logger.info(f"Mapped sampler '{sampler_name}' → '{mapped_name}'")
        return mapped_name
    
    def _create_default_workflow(self, job: DummyJobPopResponse) -> Dict[str, Any]:
        """Create a default workflow for a job when no template is available."""
        # Check if we're using a specific grid model
        if self.grid_model:
            logger.info(f"Using grid model {self.grid_model} instead of requested model {job.model}")
            
            # Map specific models to appropriate checkpoints
            if "turbovision" in self.grid_model.lower():
                model_filename = "turbovisionXL/turbovisionXL_v11.safetensors"
                logger.info(f"Using TurboVision XL model: {model_filename}")
                steps = min(job.payload.steps or 30, 4)  # Limit to 4 steps max for fast models
                cfg = min(job.payload.cfg_scale or 7.0, 2.0)  # Limit to CFG 2.0 max for fast models
            elif "sdxl_turbo" in self.grid_model.lower() or "sdxl-turbo" in self.grid_model.lower():
                model_filename = "SDXL-TURBO/sd_xl_turbo_1.0_fp16.safetensors"
                logger.info(f"Using SDXL Turbo model: {model_filename}")
                steps = min(job.payload.steps or 30, 4)  # Limit to 4 steps max for fast models
                cfg = min(job.payload.cfg_scale or 7.0, 2.0)  # Limit to CFG 2.0 max for fast models
            elif "sdxl" in self.grid_model.lower():
                model_filename = "SDXL/sd_xl_base_1.0.safetensors"
                logger.info(f"Using SDXL model: {model_filename}")
                steps = job.payload.steps or 30
                cfg = job.payload.cfg_scale or 7.0
            elif "stable_diffusion_1.5" in self.grid_model.lower() or "sd15" in self.grid_model.lower():
                model_filename = "v1-5-pruned-emaonly-fp16.safetensors"
                logger.info(f"Using Stable Diffusion 1.5 model: {model_filename}")
                steps = job.payload.steps or 30
                cfg = job.payload.cfg_scale or 7.0
            else:
                # Default to using the model mapper as fallback
                model_filename = map_model_name(self.grid_model)
                if not model_filename:
                    logger.warning(f"Unknown grid model: {self.grid_model}, using SD 1.5 as fallback")
                    model_filename = "v1-5-pruned-emaonly-fp16.safetensors"
                steps = job.payload.steps or 30
                cfg = job.payload.cfg_scale or 7.0
        else:
            # Use full path with folder prefix as shown in the error message
            model_filename = "SDXL-TURBO/sd_xl_turbo_1.0_fp16.safetensors"
            logger.info(f"No grid model specified, using SDXL Turbo: {model_filename}")
            steps = min(job.payload.steps or 30, 4)  # Limit to 4 steps max
            cfg = min(job.payload.cfg_scale or 7.0, 2.0)  # Limit to CFG 2.0 max
            
        # Ensure seed is an integer
        try:
            seed = int(job.payload.seed) if job.payload.seed else 0
        except (ValueError, TypeError):
            seed = 0
            
        # Use the _map_sampler method for consistency
        sampler_name = self._map_sampler(job.payload.sampler)
        
        # Determine appropriate resolution
        # Default to 512x512 for SD 1.5 and 1024x1024 for SDXL models
        if "sdxl" in model_filename.lower() or "turbovision" in model_filename.lower():
            default_width = 1024
            default_height = 1024
        else:
            default_width = 512
            default_height = 512
            
        # Basic workflow structure for text-to-image generation
        workflow = {
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler_name,
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": ["7", 0]
                },
                "class_type": "KSampler",
            },
            "4": {
                "inputs": {
                    "ckpt_name": model_filename
                },
                "class_type": "CheckpointLoaderSimple",
            },
            "5": {
                "inputs": {
                    "text": job.payload.prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode",
            },
            "6": {
                "inputs": {
                    "text": job.payload.negative_prompt or "",
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode",
            },
            "7": {
                "inputs": {
                    "width": job.payload.width or default_width,
                    "height": job.payload.height or default_height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage",
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode",
            },
            "9": {
                "inputs": {
                    "filename_prefix": f"horde_{job.id}",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage",
            }
        }
        
        return workflow
    
    async def _submit_workflow(self, workflow: Dict[str, Any]) -> str:
        """Submit a workflow to ComfyUI."""
        try:
            logger.info("Submitting workflow to ComfyUI...")

            # Make sure the comfy client is initialized
            if self.comfy_client is None:
                raise Exception("ComfyUI client not initialized")

            # Print workflow details
            node_count = len(workflow) if isinstance(workflow, dict) else 0
            logger.info(f"Original workflow has {node_count} nodes")
            if node_count == 0:
                logger.error("Workflow is empty!")
                raise Exception("Empty workflow")

            # Clean up workflow - remove any nodes with special IDs or missing class_type
            cleaned_workflow = {}
            for node_id, node in workflow.items():
                # Skip special node IDs like #id
                if str(node_id).startswith('#'):
                    logger.warning(f"Skipping special node ID: {node_id}")
                    continue
                    
                # Skip non-dictionary nodes
                if not isinstance(node, dict):
                    logger.warning(f"Skipping non-dictionary node: {node_id} (type: {type(node)})")
                    continue
                    
                # Skip nodes without class_type
                if 'class_type' not in node:
                    logger.warning(f"Skipping node without class_type: {node_id}")
                    continue
                
                # Ensure inputs exists
                if 'inputs' not in node:
                    logger.warning(f"Adding missing inputs to node: {node_id}")
                    node['inputs'] = {}
                
                # Keep valid nodes
                cleaned_workflow[node_id] = node

            # Extra debugging info
            if not cleaned_workflow:
                logger.error("All nodes were filtered out during cleaning!")
                # Dump the original workflow for debugging
                try:
                    debug_json = json.dumps(workflow, indent=2)
                    logger.debug(f"Original workflow JSON: {debug_json[:1000]}...")
                except Exception as e:
                    logger.error(f"Error serializing workflow for debug: {e}")
                
                # Try using the original workflow as a last resort
                cleaned_workflow = workflow

            # Prepare the payload with cleaned workflow
            payload = {
                "prompt": cleaned_workflow
            }

            # For debugging
            try:
                cleaned_count = len(cleaned_workflow) if isinstance(cleaned_workflow, dict) else 0
                logger.info(f"Cleaned workflow has {cleaned_count} nodes (removed {node_count - cleaned_count})")
                
                # Check for CLIPTextEncode nodes and log their content
                for node_id, node in cleaned_workflow.items():
                    if node.get("class_type") == "CLIPTextEncode" and "inputs" in node and "text" in node["inputs"]:
                        logger.info(f"CLIPTextEncode node {node_id} has text: {node['inputs']['text']}")
                
                # Log the full workflow for debugging (limit to 1000 chars)
                workflow_json = json.dumps(cleaned_workflow, indent=2)
                logger.info(f"Submitting workflow JSON: {workflow_json[:1000]}...")
            except Exception as e:
                logger.error(f"Error during workflow debug: {e}")

            # Submit the workflow - httpx uses await directly, not async context manager
            response = await self.comfy_client.post("/prompt", json=payload)
            
            logger.info(f"HTTP Request: POST {self.comfy_url}/prompt \"{response.status_code} {response.reason_phrase}\"")
            
            if response.status_code >= 400:
                error_content = response.text
                logger.error(f"ComfyUI error response: {error_content}")
                raise Exception(f"ComfyUI returned error {response.status_code}: {error_content}")
            
            response_data = response.json()
            
            # Extract the prompt ID
            prompt_id = response_data.get("prompt_id")
            if not prompt_id:
                raise Exception("No prompt ID in response")
            
            logger.info(f"Workflow submitted successfully with prompt ID: {prompt_id}")
            return prompt_id
            
        except httpx.HTTPError as e:
            logger.error(f"Error submitting workflow to ComfyUI: {e}")
            raise
    
    async def _wait_for_generation(self, prompt_id: str) -> Dict[str, Any]:
        """Wait for the image generation to complete."""
        logger.info(f"Waiting for generation to complete for prompt {prompt_id}...")
        
        while True:
            try:
                response = await self.comfy_client.get(f"/history/{prompt_id}")
                logger.info(f"HTTP Request: GET {self.comfy_url}/history/{prompt_id} \"{response.status_code} {response.reason_phrase}\"")
                
                response.raise_for_status()
                history = response.json()
                
                if prompt_id in history and history[prompt_id].get("outputs"):
                    logger.info("Generation completed successfully")
                    return history[prompt_id]
                
                # Check if there was an error
                if prompt_id in history and "error" in history[prompt_id]:
                    error_msg = history[prompt_id]["error"]
                    logger.error(f"ComfyUI error: {error_msg}")
                    raise RuntimeError(f"ComfyUI error: {error_msg}")
                
                # Wait before polling again
                await asyncio.sleep(1.0)
                
            except httpx.RequestError as e:
                logger.error(f"Request error while waiting for generation: {e}")
                await asyncio.sleep(2.0)
    
    async def _get_generated_image(self, result: Dict[str, Any]) -> bytes:
        """Extract the generated image from the ComfyUI result."""
        # Find the node ID of the SaveImage node (or equivalent output node)
        save_node_id = None
        logger.info(f"Looking for image in result outputs: {list(result.get('outputs', {}).keys())}")
        
        for node_id, node_output in result.get("outputs", {}).items():
            if "images" in node_output:
                save_node_id = node_id
                logger.info(f"Found image output in node {node_id}")
                break
        
        if not save_node_id:
            logger.error("No image output found in ComfyUI result")
            raise ValueError("No image output found in ComfyUI result")
        
        # Get the first image
        image_filename = result["outputs"][save_node_id]["images"][0]["filename"]
        logger.info(f"Generated image: {image_filename}")
        
        # Download the image
        image_url = f"/view?filename={image_filename}"
        logger.info(f"Downloading image from {self.comfy_url}{image_url}")
        
        response = await self.comfy_client.get(image_url)
        response.raise_for_status()
        
        logger.info(f"Downloaded image size: {len(response.content)} bytes")
        return response.content

async def main():
    """Main entry point for the bridge."""
    # Get configuration from environment variables or use defaults
    api_key = os.environ.get("GRID_API_KEY", "")
    worker_name = os.environ.get("GRID_WORKER_NAME", "ComfyUI-Bridge-Worker")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8000")  # Default to port 8000
    nsfw = os.environ.get("GRID_NSFW", "false").lower() == "true"
    threads = int(os.environ.get("GRID_THREADS", "1"))
    max_pixels = int(os.environ.get("GRID_MAX_PIXELS", "1048576"))
    api_url = os.environ.get("GRID_API_URL", "https://api.aipowergrid.io/api")
    workflow_dir = os.environ.get("WORKFLOW_DIR", os.path.join(os.getcwd(), "workflows"))
    workflow_file = os.environ.get("WORKFLOW_FILE", None)
    grid_model = os.environ.get("GRID_MODEL", None)
    
    if not api_key:
        logger.error("Error: GRID_API_KEY environment variable is required")
        return
    
    # Create and start the bridge
    bridge = ComfyUIBridge(
        api_key=api_key,
        worker_name=worker_name,
        base_url=api_url,
        nsfw=nsfw,
        threads=threads,
        max_pixels=max_pixels,
        workflow_dir=workflow_dir,
        workflow_file=workflow_file,
        grid_model=grid_model
    )
    
    await bridge.start()

if __name__ == "__main__":
    asyncio.run(main()) 