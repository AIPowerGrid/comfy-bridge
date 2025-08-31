import asyncio
import logging
import httpx
import os
from typing import List

from .api_client import APIClient
from .workflow import build_workflow
from .utils import encode_media
from .config import Settings
from .model_mapper import initialize_model_mapper, get_horde_models

logger = logging.getLogger(__name__)


class ComfyUIBridge:
    def __init__(self):
        self.api = APIClient()
        self.comfy = httpx.AsyncClient(base_url=Settings.COMFYUI_URL, timeout=300)
        self.supported_models: List[str] = []

    async def process_once(self):
        job = await self.api.pop_job(self.supported_models)
        logger.info(job["skipped"])
        job_id = job.get("id")
        if not job_id:
            print("No job ID found, skipping")
            return
        logger.info(f"Picked up job {job_id} with metadata: {job}")

        wf = await build_workflow(job)
        logger.info(f"Sending workflow to ComfyUI: {wf}")
        resp = await self.comfy.post("/prompt", json={"prompt": wf})
        if resp.status_code != 200:
            logger.error(f"ComfyUI error response: {resp.text}")
        resp.raise_for_status()
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            logger.error(f"No prompt_id for job {job_id}")
            return

        while True:
            hist = await self.comfy.get(f"/history/{prompt_id}")
            hist.raise_for_status()
            data = hist.json().get(prompt_id, {})
            outputs = data.get("outputs", {})
            if outputs:
                node_id, node_data = next(iter(outputs.items()))
                
                # Handle videos
                videos = node_data.get("videos", [])
                if videos:
                    filename = videos[0]["filename"]
                    logger.info(f"Found video file: {filename}")
                    video_resp = await self.comfy.get(f"/view?filename={filename}")
                    video_resp.raise_for_status()
                    media_bytes = video_resp.content
                    media_type = "video"  # Set media type to video
                    # Check video content length for debugging
                    logger.info(f"Video size: {len(media_bytes)} bytes")
                    break
                
                # Handle images
                imgs = node_data.get("images", [])
                if imgs:
                    filename = imgs[0]["filename"]
                    img_resp = await self.comfy.get(f"/view?filename={filename}")
                    img_resp.raise_for_status()
                    media_bytes = img_resp.content
                    media_type = "image"
                    break
                    
            await asyncio.sleep(1)

        # Check if the file has a video extension as a fallback detection method
        if 'filename' in locals() and filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
            logger.info(f"Detected video file by extension: {filename}")
            media_type = "video"

        # Check if we have an R2 upload URL
        r2_upload_url = job.get("r2_upload")
        
        # Process differently based on media type and R2 upload availability
        if media_type == "video" and r2_upload_url:
            # For videos, upload directly to Cloudflare R2 storage
            logger.info(f"Using R2 upload for video: {r2_upload_url}")
            
            try:
                # Upload the video directly to the R2 URL
                async with httpx.AsyncClient() as client:
                    headers = {"Content-Type": "video/mp4"}
                    r2_response = await client.put(r2_upload_url, content=media_bytes, headers=headers)
                    r2_response.raise_for_status()
                    logger.info(f"R2 upload successful with status {r2_response.status_code}")
                
                # Now submit a payload referencing the uploaded video
                payload = {
                    "id": job_id,
                    "state": "ok",
                    "seed": int(job.get("payload", {}).get("seed", 0)),
                    "media_type": "video",
                    "form": "video",
                    "r2_uploaded": True
                }
            except Exception as e:
                logger.error(f"Error uploading to R2: {e}")
                # Fall back to base64 encoding if R2 upload fails
                b64 = encode_media(media_bytes, media_type)
                logger.info(f"Falling back to base64 encoded {media_type} for job {job_id}")
                payload = {
                    "id": job_id,
                    "generation": b64,
                    "state": "ok",
                    "seed": int(job.get("payload", {}).get("seed", 0)),
                    "media_type": media_type,
                    "form": "video",
                    "image_type": "video/mp4"
                }
        else:
            # Standard encoding for images or when no R2 URL is available
            b64 = encode_media(media_bytes, media_type)
            logger.info(f"Encoded {media_type} for job {job_id}")
                
            payload = {
                "id": job_id,
                "generation": b64,
                "state": "ok",
                "seed": int(job.get("payload", {}).get("seed", 0)),
                "media_type": media_type  # This is crucial for Discord bot to display correctly
            }
            
            # Add filename for videos to ensure proper handling
            if media_type == "video":
                # Extract original filename and create a proper filename with extension
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                
                # Ensure the filename has the correct extension
                if not original_filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
                    original_filename += ".mp4"
                    
                payload["filename"] = original_filename
                payload["form"] = "video"
                payload["image_type"] = "video/mp4"
                
                logger.info(f"Set video parameters: filename={original_filename}, form=video")
                
        logger.info(f"Submitting {media_type} result for job {job_id}")
        await self.api.submit_result(payload)
        logger.info(
            f"Job {job_id} completed successfully with seed={payload.get('seed')}"
        )

    async def run(self):
        logger.info("Bridge starting...")
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prefer models derived from env workflows; if WORKFLOW_FILE is set, do not fall back to GRID_MODEL
        derived_models = get_horde_models()
        if Settings.WORKFLOW_FILE:
            self.supported_models = derived_models
            if not self.supported_models:
                logger.warning(
                    "No checkpoint models resolved from WORKFLOW_FILE; advertising none."
                )
        else:
            if derived_models:
                self.supported_models = derived_models
            elif Settings.GRID_MODELS:
                self.supported_models = Settings.GRID_MODELS
            else:
                self.supported_models = []
        logger.info(f"Advertising models: {self.supported_models}")

        while True:
            logger.info("Waiting for jobs...")
            try:
                await self.process_once()
            except Exception as e:
                logger.error(f"Error processing job: {e}")
            await asyncio.sleep(2)

    async def cleanup(self):
        await self.comfy.aclose()
        await self.api.client.aclose()
