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
        # Reset history check flag for new job
        if hasattr(self, '_first_history_check'):
            delattr(self, '_first_history_check')
            
        job = await self.api.pop_job(self.supported_models)
        
        # Handle the case where no job is available
        if not job or not job.get("id"):
            # This is normal - no jobs in queue
            return
            
        job_id = job.get("id")
        logger.info(f"Processing job {job_id} for model {job.get('model', 'unknown')}")
        logger.info(f"Picked up job {job_id} with metadata: {job}")
        print(f"[INFO] 🎯 Processing job {job_id} for model {job.get('model', 'unknown')}")

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

        import time
        start_time = time.time()
        max_wait_time = 600  # 10 minutes timeout
        
        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                logger.error(f"Timeout waiting for job completion after {elapsed:.0f}s")
                raise Exception(f"Job timed out after {max_wait_time}s")
            
            hist = await self.comfy.get(f"/history/{prompt_id}")
            hist.raise_for_status()
            data = hist.json().get(prompt_id, {})
            
            # Log the full history response on first check and periodically
            if not hasattr(self, '_first_history_check'):
                self._first_history_check = time.time()
                logger.info(f"First history check - Full response: {data}")
            elif int(elapsed) % 60 == 0 and int(elapsed) > 0:
                logger.info(f"History update at {elapsed:.0f}s: {data}")
            
            # Log progress every 30 seconds
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                logger.info(f"Still waiting for job completion... ({elapsed:.0f}s elapsed)")
            
            # FALLBACK: If history is empty after 30s, try checking output directory directly
            if not data and elapsed > 30:
                logger.warning(f"History empty after {elapsed:.0f}s, checking output directory...")
                expected_prefix = f"horde_{job_id}"
                try:
                    import glob
                    import os
                    # Check both output root and video subdirectory
                    search_patterns = [
                        f"{Settings.COMFYUI_OUTPUT_DIR}/{expected_prefix}*.mp4",
                        f"{Settings.COMFYUI_OUTPUT_DIR}/{expected_prefix}*.webm",
                        f"{Settings.COMFYUI_OUTPUT_DIR}/**/{expected_prefix}*.mp4",
                        f"{Settings.COMFYUI_OUTPUT_DIR}/**/{expected_prefix}*.webm",
                    ]
                    found_file = False
                    for pattern in search_patterns:
                        files = glob.glob(pattern, recursive=True)
                        if files:
                            # Found the output file!
                            video_path = files[0]
                            filename = os.path.basename(video_path)
                            logger.info(f"Found output file via filesystem: {filename}")
                            with open(video_path, 'rb') as f:
                                media_bytes = f.read()
                            media_type = "video"
                            logger.info(f"Loaded video from filesystem: {len(media_bytes)} bytes")
                            found_file = True
                            break
                    
                    if found_file:
                        # Exit the main polling loop
                        break
                    else:
                        # No file found yet
                        logger.debug(f"No output file found yet with prefix {expected_prefix}")
                except Exception as e:
                    logger.warning(f"Filesystem check failed: {e}")
            
            # Log the status for debugging
            status = data.get("status", {})
            logger.debug(f"Job status: {status}")
            
            # Check if workflow completed (status.completed exists and is not None)
            status_completed = status.get("completed", False)
            outputs = data.get("outputs", {})
            
            # Log full history response when no outputs yet
            if not outputs:
                logger.debug(f"No outputs yet. Full history response: {data}")
                # Check if the workflow has completed but failed
                if status_completed and not outputs:
                    logger.error(f"Workflow completed but no outputs found. Status: {status}")
                    raise Exception("Workflow completed without outputs")
            
            if outputs:
                logger.info(f"Found outputs: {list(outputs.keys())}")
                # Try each output node until we find media
                media_found = False
                for node_id, node_data in outputs.items():
                    logger.info(f"Checking node {node_id}: {list(node_data.keys())}")
                    
                    # Handle videos
                    videos = node_data.get("videos", [])
                    if videos:
                        filename = videos[0]["filename"]
                        logger.info(f"Found video file in node {node_id}: {filename}")
                        video_resp = await self.comfy.get(f"/view?filename={filename}")
                        video_resp.raise_for_status()
                        media_bytes = video_resp.content
                        media_type = "video"
                        logger.info(f"Video size: {len(media_bytes)} bytes")
                        media_found = True
                        break
                    
                    # Handle images
                    imgs = node_data.get("images", [])
                    if imgs:
                        filename = imgs[0]["filename"]
                        logger.info(f"Found image file in node {node_id}: {filename}")
                        img_resp = await self.comfy.get(f"/view?filename={filename}")
                        img_resp.raise_for_status()
                        media_bytes = img_resp.content
                        media_type = "image"
                        media_found = True
                        break
                
                # If we found media, exit the polling loop
                if media_found:
                    break
                    
                # No media found in any output node, keep waiting
                logger.warning(f"Outputs found but no media. Continuing to wait...")
                    
            await asyncio.sleep(1)

        # Check if the file has a video extension as a fallback detection method
        if 'filename' in locals() and filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
            logger.info(f"Detected video file by extension: {filename}")
            media_type = "video"
        
        # Ensure we're using the correct job ID from the job metadata
        job_id = job.get("id")
        r2_upload_url = job.get("r2_upload")
        
        # For videos, use the R2 upload functionality if available
        if media_type == "video" and r2_upload_url:
            logger.info(f"Using R2 upload for video: {r2_upload_url}")
            
            try:
                # Extract the actual filename from the R2 URL - it's after the last / and before the ?
                r2_filename = r2_upload_url.split('/')[-1].split('?')[0]
                logger.info(f"R2 filename extracted: {r2_filename}")
                
                # DON'T change the URL extension - it breaks the signature!
                # Instead, we'll just use the Content-Type header to specify it's an MP4
                logger.info("Using original R2 URL - will specify video/mp4 in Content-Type header")
                
                # Upload the video directly to R2 storage
                logger.info(f"Uploading video ({len(media_bytes)} bytes) to R2")
                async with httpx.AsyncClient() as client:
                    # Use video/mp4 Content-Type for the upload
                    headers = {"Content-Type": "video/mp4"}
                    r2_response = await client.put(r2_upload_url, content=media_bytes, headers=headers)
                    r2_response.raise_for_status()
                    logger.info(f"R2 upload successful: {r2_response.status_code}")
                
                # Special approach for Discord videos
                # Discord bot expects a specific payload format
                # We'll create a payload that references the URL directly
                
                # Extract the job data from r2_uploads instead of using our upload
                # This tells Discord to use its existing upload rather than our content
                r2_uploads = job.get("r2_uploads", [])
                
                # Let's try a completely different approach - encode the video directly
                # This is what worked for images, so let's try it for videos too
                b64 = encode_media(media_bytes, media_type)
                logger.info(f"Encoded video directly ({len(b64)} chars)")
                
                # Extract original filename and ensure it has the correct extension
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith('.mp4'):
                    original_filename += ".mp4"
                
                # Create a payload that matches the image format but with video-specific fields
                payload = {
                    "id": job_id,
                    "generation": b64,  # Full base64 encoded video
                    "state": "ok",
                    "seed": int(job.get("payload", {}).get("seed", 0)),
                    "filename": original_filename,
                    "form": "video",
                    "type": "video",
                    "media_type": "video"
                }
                
                # Include the original r2_uploads array if available
                if r2_uploads:
                    payload["r2_uploads"] = r2_uploads
                    logger.info(f"Including original r2_uploads URLs in payload")
                
                # Extract original filename and ensure it has the correct extension
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
                    original_filename += ".mp4"
                
                # Add the filename to the payload
                payload["filename"] = original_filename
                
                logger.info(f"Created R2 upload completion payload: id={job_id}, r2_uploaded=True")
            
            except Exception as e:
                # If R2 upload fails, we'll use a special approach for Discord videos
                logger.error(f"R2 upload failed: {e}")
                logger.info("Using alternative Discord video handling approach")
                
                # Extract the job data from r2_uploads directly
                r2_uploads = job.get("r2_uploads", [])
                
                # Use the same direct encoding approach for fallback
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith('.mp4'):
                    original_filename += ".mp4"
                
                # Encode the video directly
                b64 = encode_media(media_bytes, media_type)
                logger.info(f"Encoded video for fallback ({len(b64)} chars)")
                
                # Create the same payload structure as the main path
                payload = {
                    "id": job_id,
                    "generation": b64,
                    "state": "ok",
                    "seed": int(job.get("payload", {}).get("seed", 0)),
                    "filename": original_filename,
                    "form": "video",
                    "type": "video",
                    "media_type": "video"
                }
                
                # If we have r2_uploads info, pass it back to the API
                if r2_uploads:
                    payload["r2_uploads"] = r2_uploads
                    logger.info(f"Including original r2_uploads URLs in fallback payload")
                    
                # Create a filename for Discord
                payload["filename"] = original_filename if 'original_filename' in locals() else f"video_{job_id}.mp4"
                logger.info(f"Created Discord video fallback response for job {job_id}")
        else:
            # For images or when no R2 URL is available, use the standard approach
            b64 = encode_media(media_bytes, media_type)
            logger.info(f"Encoded {media_type} for job {job_id}")
            
            # Create the standard payload structure
            payload = {
                "id": job_id,
                "generation": b64,
                "state": "ok",
                "seed": int(job.get("payload", {}).get("seed", 0)),
                "media_type": media_type
            }
            
            # Add video-specific parameters if needed
            if media_type == "video":
                # Extract original filename and ensure it has the correct extension
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
                    original_filename += ".mp4"
                    
                # Add video-specific fields
                payload["filename"] = original_filename
                payload["form"] = "video"
                payload["type"] = "video" 
                
                logger.info(f"Added video parameters: filename={original_filename}, form=video, type=video")
        # Make sure we're logging the right media type
        logger.info(f"Submitting {payload.get('media_type', media_type)} result for job {job_id}")
        await self.api.submit_result(payload)
        logger.info(
            f"Job {job_id} completed successfully with seed={payload.get('seed')}"
        )

    async def run(self):
        logger.info("Bridge starting...")
        print(f"[INFO] 🚀 ComfyUI Bridge starting...")
        print(f"[INFO] Connecting to ComfyUI at: {Settings.COMFYUI_URL}")
        print(f"[INFO] Connecting to AI Power Grid at: {Settings.GRID_API_URL}")
        print(f"[INFO] Worker name: {Settings.GRID_WORKER_NAME}")
        
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prefer models derived from env workflows; if WORKFLOW_FILE is set, do not fall back to GRID_MODEL
        derived_models = get_horde_models()
        if Settings.WORKFLOW_FILE:
            self.supported_models = derived_models
            if not self.supported_models:
                logger.warning(
                    "No checkpoint models resolved from WORKFLOW_FILE; advertising none."
                )
                print("[WARNING] ⚠️ No models resolved from WORKFLOW_FILE!")
        else:
            if derived_models:
                self.supported_models = derived_models
                print(f"[INFO] Using models from DEFAULT_WORKFLOW_MAP: {len(derived_models)} models")
            elif Settings.GRID_MODELS:
                self.supported_models = Settings.GRID_MODELS
                print(f"[INFO] Using models from GRID_MODELS env var: {len(Settings.GRID_MODELS)} models")
            else:
                self.supported_models = []
                print("[ERROR] ❌ No models configured! Bridge won't receive any jobs!")
                
        logger.info(f"Advertising models: {self.supported_models}")
        print(f"[INFO] 📢 Advertising {len(self.supported_models)} models to AI Power Grid:")
        for i, model in enumerate(self.supported_models, 1):
            print(f"[INFO]   {i}. {model}")
            
        if not self.supported_models:
            print("[ERROR] ❌ CRITICAL: No models configured! The bridge will not receive any jobs.")
            print("[ERROR] To fix this, either:")
            print("[ERROR]   1. Set GRID_MODEL in your .env file, or")
            print("[ERROR]   2. Set WORKFLOW_FILE in your .env file, or") 
            print("[ERROR]   3. Ensure DEFAULT_WORKFLOW_MAP contains models")

        job_count = 0
        while True:
            job_count += 1
            logger.info("Waiting for jobs...")
            print(f"[INFO] 🔄 Polling for jobs (attempt #{job_count})...")
            try:
                await self.process_once()
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                print(f"[ERROR] ❌ Error processing job: {e}")
                import traceback
                print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            await asyncio.sleep(2)

    async def cleanup(self):
        await self.comfy.aclose()
        await self.api.client.aclose()