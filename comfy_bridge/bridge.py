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
        model_name = job.get('model', 'unknown')
        print(f"[JOB] 🎯 Processing job {job_id} for model {model_name}")

        wf = await build_workflow(job)
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
            
            # Log progress every 60 seconds
            if int(elapsed) % 60 == 0 and int(elapsed) > 0:
                print(f"[HEALTH] ⏱️ Job {job_id} still processing... ({elapsed:.0f}s elapsed)")
            
            # FALLBACK: If history is empty after 30s, try checking output directory directly
            if not data and elapsed > 30:
                print(f"[FALLBACK] 🔍 History empty, checking filesystem for job {job_id}...")
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
                            print(f"[SUCCESS] 📁 Found output file: {filename}")
                            with open(video_path, 'rb') as f:
                                media_bytes = f.read()
                            media_type = "video"
                            print(f"[SUCCESS] 📊 Loaded video: {len(media_bytes)} bytes")
                            found_file = True
                            break
                    
                    if found_file:
                        # Exit the main polling loop
                        break
                except Exception as e:
                    logger.warning(f"Filesystem check failed: {e}")
            
            # Check if workflow completed
            status = data.get("status", {})
            status_completed = status.get("completed", False)
            outputs = data.get("outputs", {})
            
            # Check if the workflow has completed but failed
            if status_completed and not outputs:
                logger.error(f"Workflow completed but no outputs found. Status: {status}")
                raise Exception("Workflow completed without outputs")
            
            if outputs:
                # Try each output node until we find media
                media_found = False
                for node_id, node_data in outputs.items():
                    # Handle videos
                    videos = node_data.get("videos", [])
                    if videos:
                        filename = videos[0]["filename"]
                        print(f"[SUCCESS] 🎥 Found video file: {filename}")
                        video_resp = await self.comfy.get(f"/view?filename={filename}")
                        video_resp.raise_for_status()
                        media_bytes = video_resp.content
                        media_type = "video"
                        print(f"[SUCCESS] 📊 Video size: {len(media_bytes)} bytes")
                        media_found = True
                        break
                    
                    # Handle images
                    imgs = node_data.get("images", [])
                    if imgs:
                        filename = imgs[0]["filename"]
                        print(f"[SUCCESS] 🖼️ Found image file: {filename}")
                        img_resp = await self.comfy.get(f"/view?filename={filename}")
                        img_resp.raise_for_status()
                        media_bytes = img_resp.content
                        media_type = "image"
                        print(f"[SUCCESS] 📊 Image size: {len(media_bytes)} bytes")
                        media_found = True
                        break
                
                # If we found media, exit the polling loop
                if media_found:
                    break
                    
            await asyncio.sleep(1)

        # Ensure we're using the correct job ID from the job metadata
        job_id = job.get("id")
        r2_upload_url = job.get("r2_upload")
        
        # For videos, use the R2 upload functionality if available
        if media_type == "video" and r2_upload_url:
            print(f"[UPLOAD] 📤 Uploading video to R2...")
            try:
                # Upload the video directly to R2 storage
                async with httpx.AsyncClient() as client:
                    headers = {"Content-Type": "video/mp4"}
                    r2_response = await client.put(r2_upload_url, content=media_bytes, headers=headers)
                    r2_response.raise_for_status()
                    print(f"[UPLOAD] ✅ R2 upload successful")
                
                # Create payload for video
                r2_uploads = job.get("r2_uploads", [])
                b64 = encode_media(media_bytes, media_type)
                
                # Extract original filename and ensure it has the correct extension
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith('.mp4'):
                    original_filename += ".mp4"
                
                # Create a payload that matches the image format but with video-specific fields
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
                
                # Include the original r2_uploads array if available
                if r2_uploads:
                    payload["r2_uploads"] = r2_uploads
            
            except Exception as e:
                # If R2 upload fails, fallback to direct encoding
                print(f"[UPLOAD] ⚠️ R2 upload failed, using fallback: {e}")
                r2_uploads = job.get("r2_uploads", [])
                
                # Use the same direct encoding approach for fallback
                original_filename = filename if 'filename' in locals() else f"video_{job_id}.mp4"
                if not original_filename.lower().endswith('.mp4'):
                    original_filename += ".mp4"
                
                # Encode the video directly
                b64 = encode_media(media_bytes, media_type)
                
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
        else:
            # For images or when no R2 URL is available, use the standard approach
            b64 = encode_media(media_bytes, media_type)
            
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
        
        # Submit result
        print(f"[SUBMIT] 📋 Submitting {media_type} result for job {job_id}")
        await self.api.submit_result(payload)
        print(f"[COMPLETE] ✅ Job {job_id} completed successfully (seed: {payload.get('seed')})")

    async def run(self):
        print(f"[STARTUP] 🚀 ComfyUI Bridge starting...")
        print(f"[STARTUP] 🔗 ComfyUI: {Settings.COMFYUI_URL}")
        print(f"[STARTUP] 🔗 AI Power Grid: {Settings.GRID_API_URL}")
        print(f"[STARTUP] 👤 Worker: {Settings.GRID_WORKER_NAME}")
        
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prefer models derived from env workflows; if WORKFLOW_FILE is set, do not fall back to GRID_MODEL
        derived_models = get_horde_models()
        if Settings.WORKFLOW_FILE:
            self.supported_models = derived_models
            if not self.supported_models:
                print("[ERROR] ⚠️ No models resolved from WORKFLOW_FILE!")
        else:
            if derived_models:
                self.supported_models = derived_models
            elif Settings.GRID_MODELS:
                self.supported_models = Settings.GRID_MODELS
            else:
                self.supported_models = []
                
        print(f"[STARTUP] 📢 Advertising {len(self.supported_models)} models:")
        for i, model in enumerate(self.supported_models, 1):
            print(f"[STARTUP]   {i}. {model}")
            
        if not self.supported_models:
            print("[ERROR] ❌ CRITICAL: No models configured! The bridge will not receive any jobs.")
            print("[ERROR] To fix this, either:")
            print("[ERROR]   1. Set GRID_MODEL in your .env file, or")
            print("[ERROR]   2. Set WORKFLOW_FILE in your .env file, or") 
            print("[ERROR]   3. Ensure DEFAULT_WORKFLOW_MAP contains models")

        job_count = 0
        while True:
            job_count += 1
            # Only show polling message every 10 attempts to reduce noise
            if job_count % 10 == 1:
                print(f"[HEALTH] 💓 Service running (poll #{job_count})")
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