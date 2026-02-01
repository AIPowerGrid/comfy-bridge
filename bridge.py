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
import re

# =============================================================================
# CSAM SAFETY FILTER - Text-based prompt filtering
# Blocks obvious CSAM-related keywords before generation
# Note: This is a fast gate, not the security boundary. Core should do CLIP check.
# =============================================================================

CSAM_KEYWORDS = re.compile(
    r"\b(loli|lolita|shota|shotacon|pedo|pedophile|child\s*porn|"
    r"cp\b|preteen|"
    r"underage\s*(girl|boy|sex|nude|naked)|"
    r"minor\s*(sex|nude|naked|porn)|"
    r"kid\s*(sex|nude|naked|porn)|"
    r"toddler\s*(sex|nude|naked)|"
    r"infant\s*(sex|nude|naked)|"
    r"baby\s*(sex|nude|naked))\b",
    re.IGNORECASE
)

# Matches ages 0-17 with "years old" pattern
CSAM_AGE_PATTERN = re.compile(
    r"\b(0?[0-9]|1[0-7])(?![0-9])\s*years?\s*old\b",
    re.IGNORECASE
)

def check_prompt_safety(prompt: str) -> tuple:
    """
    Check prompt for CSAM-related content.
    
    Returns:
        tuple: (is_safe: bool, reason: str)
    """
    if not prompt:
        return True, ""
    
    # Normalize: remove prompt weights like (word:1.5)
    normalized = re.sub(r"\((.*?):\d+\.?\d*\)", r"\1", prompt)
    normalized = normalized.lower()
    
    # Check for explicit CSAM keywords
    match = CSAM_KEYWORDS.search(normalized)
    if match:
        return False, f"CSAM keyword detected: {match.group()}"
    
    # Check for minor age references
    age_match = CSAM_AGE_PATTERN.search(normalized)
    if age_match:
        return False, f"Minor age reference detected: {age_match.group()}"
    
    return True, ""

# =============================================================================

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
        self.r2_upload = kwargs.get("r2_upload")  # R2 presigned upload URL
        
        # Video/i2v related fields
        self.source_image = kwargs.get("source_image")  # Base64 encoded source image for i2v
        self.source_processing = kwargs.get("source_processing", "txt2img")  # txt2img, img2img, img2video
        self.media_type = kwargs.get("media_type", "image")  # image or video
        
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
                # Video parameters
                self.length = payload_data.get("length", 121)  # Number of frames
                self.fps = payload_data.get("fps", 25)
        
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
        """Load workflow template from file. API format only."""
        if not self.workflow_file:
            logger.warning("No workflow file specified")
            return
            
        workflow_path = os.path.join(self.workflow_dir, self.workflow_file)
        if not os.path.exists(workflow_path):
            logger.error(f"Workflow file not found: {workflow_path}")
            return
            
        try:
            with open(workflow_path, 'r') as f:
                self.workflow_template = json.load(f)
            
            # Validate it's API format (dict with node IDs as keys)
            if not isinstance(self.workflow_template, dict):
                logger.error("Workflow must be a JSON object (API format)")
                self.workflow_template = None
                return
            
            # Check for web UI format (has "nodes" array) and reject it
            if "nodes" in self.workflow_template and isinstance(self.workflow_template["nodes"], list):
                logger.error("Web UI format detected - export as API format instead!")
                logger.error("In ComfyUI: Enable Dev Mode → Save (API Format)")
                self.workflow_template = None
                return
            
            # Count actual nodes (exclude _bridge metadata)
            node_count = sum(1 for k in self.workflow_template if not k.startswith("_"))
            logger.info(f"Loaded workflow: {workflow_path} ({node_count} nodes)")
            
            # Check for _bridge metadata
            if "_bridge" in self.workflow_template:
                meta = self.workflow_template["_bridge"]
                logger.info(f"  _bridge metadata found: {meta.get('name', 'unnamed')}")
                logger.info(f"  media_type: {meta.get('media_type', 'image')}")
                logger.info(f"  supports_negative: {meta.get('supports_negative', True)}")
            else:
                logger.warning("  No _bridge metadata - will use legacy node detection")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow file: {e}")
            self.workflow_template = None
        except Exception as e:
            logger.error(f"Error loading workflow: {e}")
            self.workflow_template = None
        
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
                "bridge_agent": "AI Power Grid Worker:11:https://github.com/ai-power-grid/comfy-bridge",
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
                "bridge_agent": "AI Power Grid Worker:11:https://github.com/ai-power-grid/comfy-bridge",
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
                "bridge_agent": "AI Power Grid Worker:11:https://github.com/ai-power-grid/comfy-bridge",
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
            logger.info(f"Polling for jobs... (models: {self.models})")
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("id"):  # Only log if id is truthy (not None or empty)
                        logger.info(f"🎉 Got job {data['id']}")
                    else:
                        # Debug: log why no job was returned
                        skipped = data.get("skipped", {})
                        non_zero_skipped = {k: v for k, v in skipped.items() if v > 0}
                        if non_zero_skipped:
                            logger.info(f"Jobs skipped: {non_zero_skipped}")
                        else:
                            logger.info("No jobs available (all skipped=0)")
                    return data
                else:
                    logger.error(f"Failed to pop jobs: {response.status} - {await response.text()}")
                    return None
        except Exception as e:
            logger.error(f"Error popping jobs: {e}")
            return None

    async def _upload_to_r2(self, r2_upload_url: str, media_data: bytes, content_type: str = "image/png") -> bool:
        """Upload media directly to R2 using presigned URL.
        
        Args:
            r2_upload_url: Presigned R2 upload URL
            media_data: Media data to upload (image or video)
            content_type: MIME type of the media (default: image/png)
            
        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            logger.info(f"Uploading to R2, media size: {len(media_data)} bytes, type: {content_type}")
            async with self.session.put(
                r2_upload_url,
                data=media_data,
                headers={'Content-Type': content_type}
            ) as response:
                if response.status in [200, 204]:
                    logger.info("R2 upload successful")
                    return True
                else:
                    logger.error(f"R2 upload failed: {response.status} - {await response.text()}")
                    return False
        except Exception as e:
            logger.error(f"Exception during R2 upload: {str(e)}")
            return False
    
    async def _submit_result(self, job_id: str, media_data: bytes, media_type: str = "image"):
        """Submit a completed job result to the AI Power Grid.
        
        Args:
            job_id: The job ID
            media_data: The generated media (image or video) as bytes
            media_type: Either "image" or "video"
        """
        logger.info(f"Preparing to submit {media_type} result for job {job_id}, size: {len(media_data)} bytes")
        
        # Get seed and ensure it's an integer
        seed = self.active_jobs.get(job_id, {}).get('seed', 0)
        if not isinstance(seed, int):
            try:
                seed = int(seed)
            except (ValueError, TypeError):
                seed = 0
        
        # Determine content type for R2 upload
        if media_type == "video":
            content_type = "video/mp4"  # Most common video format
        else:
            content_type = "image/png"
        
        # Check if this job requires R2 upload
        r2_upload_url = self.active_jobs.get(job_id, {}).get('r2_upload')
        
        if r2_upload_url:
            # R2 flow: Upload to R2 first
            logger.info(f"Using R2 upload flow for {media_type}")
            upload_success = await self._upload_to_r2(r2_upload_url, media_data, content_type=content_type)
            
            if not upload_success:
                logger.error("R2 upload failed, job submission aborted")
                return False
            
            # Submit completion with R2 marker (no base64 data)
            payload = {
                "id": job_id,
                "generation": "R2",  # Special marker indicating R2 upload
                "state": "ok",
                "seed": seed,
            }
        else:
            # Legacy flow: Base64 encode and submit
            logger.info(f"Using legacy base64 flow for {media_type}")
            media_base64 = base64.b64encode(media_data).decode()
            logger.info(f"Base64 encoded {media_type} size: {len(media_base64)} characters")
            
            payload = {
                "id": job_id,
                "generation": media_base64,
                "state": "ok",
                "seed": seed,
                "r2": False
            }
        
        # Add media_type for video jobs
        if media_type == "video":
            payload["media_type"] = "video"
        
        url = f"{self.base_url}/v2/generate/submit"
        logger.info(f"Submitting to API URL: {url}")
        
        try:
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                response_status = response.status
                response_text = await response.text()
                
                if response_status == 200:
                    logger.info(f"Successfully submitted {media_type} result for job {job_id}")
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
            "error": error,
            "r2": False  # Request the API to store the image in R2 and return a URL instead of base64 data
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
        # Worker is already registered in start() method, no need to register again
        logger.info("Entering main polling loop...")
        
        try:
            while self.running:
                jobs = await self._pop_jobs()
                # Check if we got a job (has 'id' field) - don't check skipped dict as it's always present
                if jobs and jobs.get("id"):
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
        source_processing = job.source_processing or "txt2img"
        expected_media_type = job.media_type or "image"
        
        logger.info(f"Processing job {job_id} with model {job.model}")
        logger.info(f"  source_processing: {source_processing}, media_type: {expected_media_type}")
        
        # === SAFETY CHECK: Block CSAM-related prompts before generation ===
        prompt_text = job.payload.prompt or ""
        is_safe, safety_reason = check_prompt_safety(prompt_text)
        if not is_safe:
            logger.warning(f"🚫 Job {job_id} BLOCKED: {safety_reason}")
            logger.warning(f"   Prompt was: {prompt_text[:100]}...")
            await self._submit_failure(job_id, f"Content policy violation: {safety_reason}")
            return
        # === END SAFETY CHECK ===
        
        try:
            # Store job information in active_jobs dictionary
            # Generate a random seed if none is provided
            seed = 0
            if hasattr(job.payload, 'seed') and job.payload.seed is not None:
                try:
                    seed = int(job.payload.seed)
                    logger.info(f"Using provided seed: {seed}")
                except (ValueError, TypeError):
                    # If seed conversion fails, use a random seed
                    import random
                    seed = random.randint(1, 2**32-1)
                    logger.info(f"Invalid seed provided, generated random seed: {seed}")
            else:
                # Generate a random seed
                import random
                seed = random.randint(1, 2**32-1)
                logger.info(f"No seed provided, generated random seed: {seed}")
            
            # Handle source image for img2img/img2video jobs
            source_image_filename = None
            if job.source_image and source_processing in ["img2img", "img2video", "img2vid"]:
                logger.info(f"Job has source_image for {source_processing}, uploading to ComfyUI...")
                source_image_filename = await self._save_source_image(job.source_image, job_id)
                logger.info(f"Source image saved as: {source_image_filename}")
            
            self.active_jobs[job_id] = {
                'seed': seed,
                'model': job.model,
                'kudos': job.kudos or 0,
                'r2_upload': job.r2_upload,  # Store R2 upload URL if present
                'source_image_filename': source_image_filename,
                'media_type': expected_media_type,
            }
            
            # Convert AI Power Grid job to ComfyUI workflow
            workflow = self._convert_job_to_workflow(job)
            
            # Submit workflow to ComfyUI
            prompt_id = await self._submit_workflow(workflow)
            
            # Wait for the generation to complete
            result = await self._wait_for_generation(prompt_id)
            
            # Get the generated media (image or video)
            media_data, media_type, filename = await self._get_generated_media(result)
            logger.info(f"Generated {media_type}: {filename} ({len(media_data)} bytes)")
            
            # Submit the result back to the AI Power Grid
            await self._submit_result(job_id, media_data, media_type=media_type)
            
            # Track stats
            self.jobs_completed += 1
            self.total_kudos += job.kudos or 0
            
            logger.info(f"Job {job_id} completed successfully (earned {job.kudos} kudos)")
            
            # Clean up active job
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
            
            # Check if workflow has _bridge metadata (new clean format)
            if "_bridge" in self.workflow_template:
                logger.info("Using new _bridge metadata format")
                return self._update_workflow_with_metadata(self.workflow_template, job)
            else:
                logger.info("Using legacy workflow detection")
                return self._update_workflow_legacy(self.workflow_template, job)
        
        # Otherwise fall back to default workflow
        logger.warning(f"No workflow template loaded, falling back to default workflow for {job.model}")
        return self._create_default_workflow(job)
    
    def _update_workflow_with_metadata(self, workflow: Dict[str, Any], job: DummyJobPopResponse) -> Dict[str, Any]:
        """
        Update workflow using _bridge metadata. Clean, declarative, no node hunting.
        
        The _bridge section tells us exactly which nodes to update:
        {
            "_bridge": {
                "version": 1,
                "nodes": {"prompt": "58", "sampler": "3", "latent": "5", "output": "9"},
                "fields": {"prompt": "value", "seed": "seed", ...},
                "supports_negative": false,
                "media_type": "image"
            }
        }
        """
        import random
        
        # Deep copy to avoid modifying template
        w = json.loads(json.dumps(workflow))
        
        # Extract and remove metadata (don't send to ComfyUI)
        meta = w.pop("_bridge", None)
        if not meta:
            logger.error("_update_workflow_with_metadata called but no _bridge found!")
            return self._update_workflow_legacy(w, job)
        
        nodes = meta.get("nodes", {})
        fields = meta.get("fields", {})
        
        # === PROMPT ===
        prompt_node_id = nodes.get("prompt")
        prompt_field = fields.get("prompt", "text")
        if prompt_node_id and prompt_node_id in w:
            # Handle ### delimiter for positive/negative split
            prompt_text = job.payload.prompt or ""
            if "###" in prompt_text:
                prompt_text = prompt_text.split("###")[0].strip()
            w[prompt_node_id]["inputs"][prompt_field] = prompt_text
            logger.info(f"Set prompt in node {prompt_node_id}: {prompt_text[:50]}...")
        
        # === NEGATIVE PROMPT ===
        if meta.get("supports_negative", True):
            neg_node_id = nodes.get("negative_prompt")
            neg_field = fields.get("negative_prompt", "text")
            if neg_node_id and neg_node_id in w:
                neg_text = job.payload.negative_prompt or ""
                # Also check for ### delimiter
                if "###" in (job.payload.prompt or ""):
                    parts = job.payload.prompt.split("###", 1)
                    if len(parts) > 1 and not neg_text:
                        neg_text = parts[1].strip()
                w[neg_node_id]["inputs"][neg_field] = neg_text
                logger.info(f"Set negative prompt in node {neg_node_id}")
        
        # === SEED ===
        sampler_node_id = nodes.get("sampler")
        seed_field = fields.get("seed", "seed")
        if sampler_node_id and sampler_node_id in w:
            if hasattr(job.payload, 'seed') and job.payload.seed is not None:
                try:
                    seed = int(job.payload.seed)
                except (ValueError, TypeError):
                    seed = random.randint(1, 2**32-1)
            else:
                seed = random.randint(1, 2**32-1)
            w[sampler_node_id]["inputs"][seed_field] = seed
            logger.info(f"Set seed in node {sampler_node_id}: {seed}")
            
            # Store seed in active_jobs
            self.active_jobs[job.id] = self.active_jobs.get(job.id, {})
            self.active_jobs[job.id]['seed'] = seed
        
        # === SAMPLER PARAMS (steps, cfg, sampler) ===
        # Grid sends params, we use them
        if sampler_node_id and sampler_node_id in w:
            sampler_inputs = w[sampler_node_id]["inputs"]
            
            # Steps
            if hasattr(job.payload, 'steps') and job.payload.steps:
                sampler_inputs["steps"] = job.payload.steps
                logger.info(f"Set steps: {job.payload.steps}")
            
            # CFG Scale
            if hasattr(job.payload, 'cfg_scale') and job.payload.cfg_scale:
                sampler_inputs["cfg"] = job.payload.cfg_scale
                logger.info(f"Set cfg: {job.payload.cfg_scale}")
            
            # Sampler name
            if hasattr(job.payload, 'sampler') and job.payload.sampler:
                mapped_sampler = self._map_sampler(job.payload.sampler)
                sampler_inputs["sampler_name"] = mapped_sampler
                logger.info(f"Set sampler: {mapped_sampler}")
        
        # === DIMENSIONS ===
        latent_node_id = nodes.get("latent")
        if latent_node_id and latent_node_id in w:
            width_field = fields.get("width", "width")
            height_field = fields.get("height", "height")
            if job.payload.width:
                w[latent_node_id]["inputs"][width_field] = job.payload.width
            if job.payload.height:
                w[latent_node_id]["inputs"][height_field] = job.payload.height
            logger.info(f"Set dimensions in node {latent_node_id}: {job.payload.width}x{job.payload.height}")
        
        # === OUTPUT FILENAME ===
        output_node_id = nodes.get("output")
        if output_node_id and output_node_id in w:
            w[output_node_id]["inputs"]["filename_prefix"] = f"aipg_{job.id}"
            logger.info(f"Set output filename prefix: aipg_{job.id}")
        
        # === SOURCE IMAGE (img2img) ===
        source_image_node_id = nodes.get("source_image")
        if source_image_node_id and source_image_node_id in w:
            source_filename = self.active_jobs.get(job.id, {}).get('source_image_filename')
            if source_filename:
                w[source_image_node_id]["inputs"]["image"] = source_filename
                logger.info(f"Set source image: {source_filename}")
        
        # === VIDEO PARAMS ===
        video_latent_node_id = nodes.get("video_latent")
        if video_latent_node_id and video_latent_node_id in w:
            if hasattr(job.payload, 'length') and job.payload.length:
                w[video_latent_node_id]["inputs"]["length"] = job.payload.length
                logger.info(f"Set video length: {job.payload.length} frames")
        
        logger.info(f"Workflow updated via _bridge metadata ({len(w)} nodes)")
        return w
    
    def _update_workflow_legacy(self, workflow: Dict[str, Any], job: DummyJobPopResponse) -> Dict[str, Any]:
        """
        LEGACY: Update workflow by scanning nodes and guessing which is which.
        Use _update_workflow_with_metadata() for new workflows with _bridge section.
        """
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
                
                # Update seed in KSampler node if job has seed
                if hasattr(job.payload, 'seed') and job.payload.seed is not None:
                    try:
                        seed = int(job.payload.seed)
                        node["inputs"]["seed"] = seed
                        logger.info(f"Updated seed in KSampler node to {seed}")
                    except (ValueError, TypeError):
                        # If conversion fails, generate a random seed
                        import random
                        seed = random.randint(1, 2**32-1)
                        node["inputs"]["seed"] = seed
                        logger.info(f"Generated random seed for KSampler node: {seed}")
                else:
                    # Generate a random seed if none provided
                    import random
                    seed = random.randint(1, 2**32-1)
                    node["inputs"]["seed"] = seed
                    logger.info(f"No seed in job, generated random seed for KSampler node: {seed}")
                
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
        
        # === Z-Image-Turbo and similar workflows: Handle PrimitiveStringMultiline nodes ===
        # These workflows use PrimitiveStringMultiline as the prompt source instead of direct CLIPTextEncode
        primitive_prompt_updated = False
        has_conditioning_zero_out = False
        
        # First pass: detect workflow type
        for node_id, node in updated_workflow.items():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") == "ConditioningZeroOut":
                has_conditioning_zero_out = True
                break
        
        # Second pass: update prompts
        for node_id, node in updated_workflow.items():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") == "PrimitiveStringMultiline":
                # Check if this node's output connects to a CLIPTextEncode (it's a prompt source)
                if "inputs" in node and "value" in node["inputs"]:
                    node["inputs"]["value"] = positive_prompt
                    primitive_prompt_updated = True
                    logger.info(f"Set prompt in PrimitiveStringMultiline node {node_id}: {positive_prompt[:50]}...")
                elif "inputs" in node:
                    # Some versions might not have 'value' key yet
                    node["inputs"]["value"] = positive_prompt
                    primitive_prompt_updated = True
                    logger.info(f"Added prompt to PrimitiveStringMultiline node {node_id}: {positive_prompt[:50]}...")
        
        if primitive_prompt_updated:
            logger.info("Detected PrimitiveStringMultiline workflow (Z-Image-Turbo style)")
        
        # Log warning if negative prompt provided but workflow doesn't support it
        if has_conditioning_zero_out and negative_prompt:
            logger.warning(f"Workflow uses ConditioningZeroOut - negative prompts are NOT supported")
            logger.warning(f"Ignoring negative prompt: '{negative_prompt[:50]}...'")
            negative_prompt = ""  # Clear it so we don't try to set it anywhere
        
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
                # Check if text input is a connection reference (list like ["node_id", slot])
                # If so, skip - the prompt comes from another node (e.g., PrimitiveStringMultiline)
                text_is_connection = isinstance(node["inputs"].get("text"), list)
                
                if text_is_connection:
                    logger.info(f"CLIPTextEncode node {node_id} gets text from connection, skipping direct update")
                    continue
                
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
            
            # Update EmptyLatentImage or EmptySD3LatentImage node with resolution from job
            elif node.get("class_type") in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                if job.payload.width:
                    node["inputs"]["width"] = job.payload.width
                    logger.info(f"Set {node.get('class_type')} width to {job.payload.width}")
                if job.payload.height:
                    node["inputs"]["height"] = job.payload.height
                    logger.info(f"Set {node.get('class_type')} height to {job.payload.height}")
            
            # Only update SaveImage node to set filename with job ID
            elif node.get("class_type") == "SaveImage":
                node["inputs"]["filename_prefix"] = f"horde_{job.id}"
                logger.info(f"Set SaveImage filename prefix to horde_{job.id}")
            
            # Update SaveVideo node to set filename with job ID
            elif node.get("class_type") in ["SaveVideo", "VHS_VideoCombine"]:
                if "filename_prefix" in node.get("inputs", {}):
                    node["inputs"]["filename_prefix"] = f"video/horde_{job.id}"
                    logger.info(f"Set {node.get('class_type')} filename prefix to video/horde_{job.id}")
            
            # Handle LoadImage nodes for img2img/img2video source images
            elif node.get("class_type") == "LoadImage":
                # Check if we have a source image for this job
                source_image_filename = self.active_jobs.get(job.id, {}).get('source_image_filename')
                if source_image_filename:
                    node["inputs"]["image"] = source_image_filename
                    logger.info(f"Set LoadImage node {node_id} to use source image: {source_image_filename}")
            
            # Handle LTXVScheduler nodes - update steps if provided
            elif node.get("class_type") == "LTXVScheduler":
                if job.payload.steps and job.payload.steps != 30:  # Only if non-default
                    node["inputs"]["steps"] = job.payload.steps
                    logger.info(f"Set LTXVScheduler steps to {job.payload.steps}")
            
            # Handle EmptyLTXVLatentVideo - update frames if provided
            elif node.get("class_type") == "EmptyLTXVLatentVideo":
                if hasattr(job.payload, 'length') and job.payload.length:
                    node["inputs"]["length"] = job.payload.length
                    logger.info(f"Set EmptyLTXVLatentVideo length to {job.payload.length} frames")
                if job.payload.width:
                    node["inputs"]["width"] = job.payload.width
                if job.payload.height:
                    node["inputs"]["height"] = job.payload.height
            
            # Handle RandomNoise nodes - set seed
            elif node.get("class_type") == "RandomNoise":
                if "noise_seed" in node.get("inputs", {}):
                    # Use the job seed if available, or generate a new one
                    job_seed = self.active_jobs.get(job.id, {}).get('seed')
                    if job_seed is None:
                        import random
                        job_seed = random.randint(1, 2**32-1)
                        logger.info(f"Generated random seed for RandomNoise: {job_seed}")
                    node["inputs"]["noise_seed"] = job_seed
                    logger.info(f"Set RandomNoise seed to {job_seed}")
                
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
            # If seed is provided, use it; otherwise generate a random seed between 1 and 2^32-1
            if hasattr(job.payload, 'seed') and job.payload.seed is not None:
                seed = int(job.payload.seed)
                logger.info(f"Using provided seed: {seed}")
            else:
                # Generate a random seed (not 0)
                import random
                seed = random.randint(1, 2**32-1)
                logger.info(f"No seed provided, generated random seed: {seed}")
        except (ValueError, TypeError):
            # If seed conversion fails, use a random seed
            import random
            seed = random.randint(1, 2**32-1)
            logger.info(f"Invalid seed provided, generated random seed: {seed}")
            
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
    
    async def _get_generated_media(self, result: Dict[str, Any]) -> tuple:
        """Extract the generated image or video from the ComfyUI result.
        
        Returns:
            tuple: (media_data: bytes, media_type: str, filename: str)
                   media_type is either "image" or "video"
        """
        logger.info(f"Looking for media in result outputs: {list(result.get('outputs', {}).keys())}")
        
        # First check for video output (SaveVideo, VHS_VideoCombine, etc.)
        for node_id, node_output in result.get("outputs", {}).items():
            if "gifs" in node_output:
                # VHS_VideoCombine and similar nodes output to "gifs" (can be mp4, webm, gif)
                video_info = node_output["gifs"][0]
                video_filename = video_info.get("filename")
                subfolder = video_info.get("subfolder", "")
                
                logger.info(f"Found video output in node {node_id}: {video_filename}")
                
                # Download the video
                if subfolder:
                    video_url = f"/view?filename={video_filename}&subfolder={subfolder}&type=output"
                else:
                    video_url = f"/view?filename={video_filename}&type=output"
                
                logger.info(f"Downloading video from {self.comfy_url}{video_url}")
                response = await self.comfy_client.get(video_url)
                response.raise_for_status()
                
                logger.info(f"Downloaded video size: {len(response.content)} bytes")
                return response.content, "video", video_filename
            
            if "videos" in node_output:
                # SaveVideo nodes output to "videos"
                video_info = node_output["videos"][0]
                video_filename = video_info.get("filename")
                subfolder = video_info.get("subfolder", "")
                
                logger.info(f"Found video output in node {node_id}: {video_filename}")
                
                # Download the video
                if subfolder:
                    video_url = f"/view?filename={video_filename}&subfolder={subfolder}&type=output"
                else:
                    video_url = f"/view?filename={video_filename}&type=output"
                
                logger.info(f"Downloading video from {self.comfy_url}{video_url}")
                response = await self.comfy_client.get(video_url)
                response.raise_for_status()
                
                logger.info(f"Downloaded video size: {len(response.content)} bytes")
                return response.content, "video", video_filename
        
        # Fall back to image output
        for node_id, node_output in result.get("outputs", {}).items():
            if "images" in node_output:
                logger.info(f"Found image output in node {node_id}")
                
                # Get the first image
                image_filename = node_output["images"][0]["filename"]
                subfolder = node_output["images"][0].get("subfolder", "")
                logger.info(f"Generated image: {image_filename}")
                
                # Download the image
                if subfolder:
                    image_url = f"/view?filename={image_filename}&subfolder={subfolder}&type=output"
                else:
                    image_url = f"/view?filename={image_filename}"
                
                logger.info(f"Downloading image from {self.comfy_url}{image_url}")
                response = await self.comfy_client.get(image_url)
                response.raise_for_status()
                
                logger.info(f"Downloaded image size: {len(response.content)} bytes")
                return response.content, "image", image_filename
        
        logger.error("No media output found in ComfyUI result")
        raise ValueError("No media output found in ComfyUI result")
    
    async def _get_generated_image(self, result: Dict[str, Any]) -> bytes:
        """Extract the generated image from the ComfyUI result (legacy compatibility)."""
        media_data, media_type, filename = await self._get_generated_media(result)
        return media_data
    
    async def _save_source_image(self, source_image_base64: str, job_id: str) -> str:
        """Save a base64 encoded source image to ComfyUI's input folder.
        
        Returns:
            str: The filename of the saved image
        """
        import uuid
        
        # Decode the base64 image
        try:
            image_data = base64.b64decode(source_image_base64)
        except Exception as e:
            logger.error(f"Failed to decode source image: {e}")
            raise
        
        # Generate a unique filename
        filename = f"input_{job_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Get the ComfyUI input folder path
        # We'll upload via the API
        try:
            # Use ComfyUI's upload endpoint
            files = {
                'image': (filename, image_data, 'image/png')
            }
            
            # httpx doesn't support files in the same way as requests, use a workaround
            from io import BytesIO
            upload_url = f"{self.comfy_url}/upload/image"
            
            # Use requests for multipart upload (httpx async multipart is more complex)
            import requests as sync_requests
            response = sync_requests.post(
                upload_url,
                files={'image': (filename, BytesIO(image_data), 'image/png')},
                data={'overwrite': 'true'}
            )
            
            if response.status_code == 200:
                result = response.json()
                saved_filename = result.get('name', filename)
                logger.info(f"Uploaded source image to ComfyUI: {saved_filename}")
                return saved_filename
            else:
                logger.error(f"Failed to upload source image: {response.status_code} {response.text}")
                raise RuntimeError(f"Failed to upload source image: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error uploading source image to ComfyUI: {e}")
            raise

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