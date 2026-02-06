import asyncio
import logging
import httpx
import os
from typing import List, Dict, Any

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
        
        # Handle new batch format - check for ids array first
        job_ids = job.get("ids", [])
        job_id = job.get("id")
        
        if not job_id and not job_ids:
            print("No job ID found, skipping")
            return
        
        # Get batch parameters
        payload = job.get("payload", {})
        batch_size = payload.get("batch_size", 1)
        
        # Generate random seeds for each batch item if not provided
        import random
        base_seed = payload.get("seed", 0)
        provided_seeds = payload.get("seeds")
        if provided_seeds and len(provided_seeds) >= batch_size:
            seeds = provided_seeds[:batch_size]
        else:
            # Generate unique random seeds for each batch item
            seeds = [random.randint(1, 2**32 - 1) for _ in range(batch_size)]
            logger.info(f"Generated random seeds for batch: {seeds}")
        
        r2_uploads = job.get("r2_uploads", [])
        
        # Ensure we have the right number of IDs and URLs
        if not job_ids:
            job_ids = [job_id]
        if not r2_uploads and job.get("r2_upload"):
            r2_uploads = [job.get("r2_upload")]
        
        logger.info(f"Picked up batch job with {batch_size} images, ids: {job_ids}")

        # Build workflow with batch support
        wf = await build_workflow(job)
        logger.info(f"Sending workflow to ComfyUI (batch_size={batch_size}): {wf}")
        resp = await self.comfy.post("/prompt", json={"prompt": wf})
        if resp.status_code != 200:
            logger.error(f"ComfyUI error response: {resp.text}")
        resp.raise_for_status()
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            logger.error(f"No prompt_id for batch job")
            return

        # Wait for generation to complete
        media_items = []  # List of (media_bytes, media_type, filename)
        while True:
            hist = await self.comfy.get(f"/history/{prompt_id}")
            hist.raise_for_status()
            data = hist.json().get(prompt_id, {})
            outputs = data.get("outputs", {})
            if outputs:
                node_id, node_data = next(iter(outputs.items()))
                
                # Handle videos (batch of 1 for video)
                videos = node_data.get("videos", [])
                if videos:
                    for video_info in videos:
                        filename = video_info["filename"]
                        logger.info(f"Found video file: {filename}")
                        video_resp = await self.comfy.get(f"/view?filename={filename}")
                        video_resp.raise_for_status()
                        media_items.append((video_resp.content, "video", filename))
                    break
                
                # Handle batched images
                imgs = node_data.get("images", [])
                if imgs:
                    logger.info(f"Found {len(imgs)} images in batch")
                    for img_info in imgs:
                        filename = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        if subfolder:
                            img_url = f"/view?filename={filename}&subfolder={subfolder}"
                        else:
                            img_url = f"/view?filename={filename}"
                        img_resp = await self.comfy.get(img_url)
                        img_resp.raise_for_status()
                        media_items.append((img_resp.content, "image", filename))
                    break
                    
            await asyncio.sleep(1)

        logger.info(f"Generated {len(media_items)} media items for batch")

        # Process each media item and submit results
        for i, (media_bytes, media_type, filename) in enumerate(media_items):
            # Get corresponding job ID, seed, and R2 URL for this item
            item_job_id = job_ids[i] if i < len(job_ids) else job_ids[0]
            item_seed = seeds[i] if i < len(seeds) else seeds[0]
            item_r2_url = r2_uploads[i] if i < len(r2_uploads) else None
            
            logger.info(f"Processing item {i+1}/{len(media_items)}: id={item_job_id}, seed={item_seed}")
            
            # Upload to R2 if URL is available
            if item_r2_url:
                try:
                    content_type = "video/mp4" if media_type == "video" else "image/webp"
                    async with httpx.AsyncClient() as client:
                        r2_response = await client.put(item_r2_url, content=media_bytes, headers={"Content-Type": content_type})
                        r2_response.raise_for_status()
                        logger.info(f"R2 upload successful for item {i+1}")
                    
                    # Submit with R2 marker
                    result_payload = {
                        "id": item_job_id,
                        "generation": "R2",
                        "state": "ok",
                        "seed": int(item_seed),
                        "media_type": media_type
                    }
                except Exception as e:
                    logger.error(f"R2 upload failed for item {i+1}: {e}, falling back to base64")
                    b64 = encode_media(media_bytes, media_type)
                    result_payload = {
                        "id": item_job_id,
                        "generation": b64,
                        "state": "ok",
                        "seed": int(item_seed),
                        "media_type": media_type
                    }
            else:
                # No R2 URL, use base64
                b64 = encode_media(media_bytes, media_type)
                result_payload = {
                    "id": item_job_id,
                    "generation": b64,
                    "state": "ok",
                    "seed": int(item_seed),
                    "media_type": media_type
                }
            
            # Add video-specific fields if needed
            if media_type == "video":
                result_payload["filename"] = filename if filename.lower().endswith(('.mp4', '.webm')) else f"{filename}.mp4"
                result_payload["form"] = "video"
                result_payload["type"] = "video"
            
            # Submit this item's result
            await self.api.submit_result(result_payload)
            logger.info(f"Submitted result for job {item_job_id} with seed={item_seed}")
        
        logger.info(f"Batch job completed: {len(media_items)} items processed")

    async def run(self):
        logger.info("Bridge starting...")
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prioritize GRID_MODELS if set, otherwise use derived models from workflows
        derived_models = get_horde_models()
        if Settings.GRID_MODELS:
            # Use GRID_MODELS if explicitly set
            self.supported_models = Settings.GRID_MODELS
            logger.info(f"Using GRID_MODELS from config: {self.supported_models}")
        elif Settings.WORKFLOW_FILE:
            self.supported_models = derived_models
            if not self.supported_models:
                logger.warning(
                    "No checkpoint models resolved from WORKFLOW_FILE; advertising none."
                )
        else:
            if derived_models:
                self.supported_models = derived_models
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