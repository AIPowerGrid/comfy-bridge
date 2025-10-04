import asyncio
import logging
import httpx
import os
import json
import websockets
from typing import List

from .api_client import APIClient
from .workflow import build_workflow
from .utils import encode_media
from .config import Settings
from .model_mapper import initialize_model_mapper, get_horde_models

logger = logging.getLogger(__name__)

# Completely disable httpx logging to stop HTTP request spam
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)


class ComfyUIBridge:
    def __init__(self):
        self.api = APIClient()
        self.comfy = httpx.AsyncClient(base_url=Settings.COMFYUI_URL, timeout=300)
        self.supported_models: List[str] = []
        # Track jobs currently being processed to prevent duplicates
        self.processing_jobs: set = set()

    async def process_once(self):
        # Reset history check flag for new job
        if hasattr(self, '_first_history_check'):
            delattr(self, '_first_history_check')
        # Reset filesystem check flag for new job
        if hasattr(self, '_filesystem_checked'):
            delattr(self, '_filesystem_checked')
            
        job = await self.api.pop_job(self.supported_models)
        
        # Handle the case where no job is available
        if not job or not job.get("id"):
            # This is normal - no jobs in queue
            return
            
        job_id = job.get("id")
        model_name = job.get('model', 'unknown')
        
        # Check if we're already processing this job (prevent duplicates)
        if job_id in self.processing_jobs:
            print(f"[JOB] ⚠️ Job {job_id} already being processed, skipping duplicate")
            return
            
        # Mark job as being processed
        self.processing_jobs.add(job_id)
        print(f"[JOB] 🎯 Processing job {job_id} for model {model_name}")
        
        try:
            wf = await build_workflow(job)
            resp = await self.comfy.post("/prompt", json={"prompt": wf})
            if resp.status_code != 200:
                logger.error(f"ComfyUI error response: {resp.text}")
            resp.raise_for_status()
            prompt_id = resp.json().get("prompt_id")
            if not prompt_id:
                logger.error(f"No prompt_id for job {job_id}")
                return

            # Start WebSocket listener for ComfyUI logs
            websocket_task = asyncio.create_task(self.listen_comfyui_logs(prompt_id))
            
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
                
                # Show fallback health check every 30 seconds (if WebSocket fails)
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    print(f"[COMFYUI] processing... ({elapsed:.0f}s)")
                
                # FALLBACK: If history is empty after 2 minutes OR we're stuck with incomplete files, try filesystem
                if (not data and elapsed > 120) or (data and elapsed > 120 and not hasattr(self, '_filesystem_checked')):
                    self._filesystem_checked = True  # Mark that we've checked filesystem for this job
                    print(f"[FALLBACK] 🔍 Checking filesystem for complete video for job {job_id}...")
                    expected_prefix = f"horde_{job_id}"
                    try:
                        import glob
                        import os
                        # Check both output root and video subdirectory with multiple patterns
                        search_patterns = [
                            f"{Settings.COMFYUI_OUTPUT_DIR}/{expected_prefix}*.mp4",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/{expected_prefix}*.webm",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/**/{expected_prefix}*.mp4",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/**/{expected_prefix}*.webm",
                            # Also check for files without the exact prefix (in case naming changed)
                            f"{Settings.COMFYUI_OUTPUT_DIR}/*{job_id}*.mp4",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/*{job_id}*.webm",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/**/*{job_id}*.mp4",
                            f"{Settings.COMFYUI_OUTPUT_DIR}/**/*{job_id}*.webm",
                        ]
                        found_file = False
                        all_video_files = []
                        for pattern in search_patterns:
                            files = glob.glob(pattern, recursive=True)
                            if files:
                                print(f"[DEBUG] 🔍 Found {len(files)} files matching pattern: {pattern}")
                                for file_path in files:
                                    filename = os.path.basename(file_path)
                                    if filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
                                        # Get file size
                                        try:
                                            file_size = os.path.getsize(file_path)
                                            all_video_files.append((file_path, filename, file_size))
                                            print(f"[DEBUG] 📹 Video file: {filename} ({file_size} bytes)")
                                        except Exception as e:
                                            print(f"[DEBUG] ⚠️ Could not get size for {filename}: {e}")
                        
                        if all_video_files:
                            # Sort by file size (largest first) and pick the biggest one
                            all_video_files.sort(key=lambda x: x[2], reverse=True)
                            video_path, filename, file_size = all_video_files[0]
                            print(f"[DEBUG] 🎯 Selected largest video file: {filename} ({file_size} bytes)")
                            
                            # Since we already filtered for video files, we know this is a video
                            media_type = "video"
                            
                            with open(video_path, 'rb') as f:
                                media_bytes = f.read()
                            
                            # Validate file size - skip if too small (likely incomplete)
                            if media_type == "video" and len(media_bytes) < 1 * 1024 * 1024:  # Less than 1MB
                                continue  # Skip silently to reduce log spam
                            
                            print(f"[SUCCESS] 📊 Loaded {media_type}: {len(media_bytes)} bytes")
                            
                            # For videos, wait a bit more to ensure the file is completely written
                            if media_type == "video":
                                print(f"[WAIT] ⏳ Waiting 10 seconds to ensure video is completely written...")
                                await asyncio.sleep(10)
                                # Re-read the file to check if size changed
                                with open(video_path, 'rb') as f:
                                    new_media_bytes = f.read()
                                if len(new_media_bytes) != len(media_bytes):
                                    print(f"[UPDATE] 📈 Video size changed from {len(media_bytes)} to {len(new_media_bytes)} bytes - using updated file")
                                    media_bytes = new_media_bytes
                            
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
                
                # Debug logging to see what's happening (only once)
                if elapsed > 60 and not hasattr(self, '_debug_logged'):
                    self._debug_logged = True
                    print(f"[DEBUG] Status: {status}")
                    print(f"[DEBUG] Outputs keys: {list(outputs.keys()) if outputs else 'None'}")
                    if outputs:
                        for node_id, node_data in outputs.items():
                            print(f"[DEBUG] Node {node_id}: {list(node_data.keys())}")
                            if "videos" in node_data:
                                print(f"[DEBUG] Videos in node {node_id}: {node_data['videos']}")
                            if "images" in node_data:
                                print(f"[DEBUG] Images in node {node_id}: {node_data['images']}")
                
                # Check for execution errors in the status
                if status_completed and status.get("status_str") == "error":
                    error_msg = status.get("exception_message", "Unknown execution error")
                    print(f"[COMFYUI] ❌ Workflow failed: {error_msg}")
                    raise Exception(f"ComfyUI workflow failed: {error_msg}")
                
                # Check if the workflow has completed but failed
                if status_completed and not outputs:
                    logger.error(f"Workflow completed but no outputs found. Status: {status}")
                    raise Exception("Workflow completed without outputs")
                
                if outputs and status_completed:
                    # Only process outputs when the workflow is truly completed
                    # This ensures we get the final video, not an interrupted one
                    media_found = False
                    for node_id, node_data in outputs.items():
                        # Handle videos
                        videos = node_data.get("videos", [])
                        if videos:
                            filename = videos[0]["filename"]
                            
                            # Check if this is a complete video by file size
                            # Skip videos that are likely incomplete (too small or from interrupted prompts)
                            video_resp = await self.comfy.get(f"/view?filename={filename}")
                            video_resp.raise_for_status()
                            media_bytes = video_resp.content
                            
                            # Only accept videos that are reasonably sized (at least 1MB for complete videos)
                            # This helps filter out incomplete/interrupted videos
                            if len(media_bytes) < 1 * 1024 * 1024:  # Less than 1MB
                                continue  # Skip silently to reduce log spam
                            
                            print(f"[SUCCESS] 🎥 Found complete video file: {filename}")
                            media_type = "video"
                            print(f"[SUCCESS] 📊 Video size: {len(media_bytes)} bytes")
                            media_found = True
                            break
                        
                        # Handle images (but check if they're actually videos)
                        imgs = node_data.get("images", [])
                        if imgs:
                            filename = imgs[0]["filename"]
                            
                            # Check file extension to determine if it's actually a video
                            if filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
                                print(f"[DEBUG] 🎥 Found video file in images array: {filename}")
                                # It's a video file in the images array
                                try:
                                    video_resp = await self.comfy.get(f"/view?filename={filename}")
                                    video_resp.raise_for_status()
                                    media_bytes = video_resp.content
                                    
                                    print(f"[DEBUG] 📊 Video file size: {len(media_bytes)} bytes")
                                    
                                    # Only accept videos that are reasonably sized (at least 1MB for complete videos)
                                    # This helps filter out incomplete/interrupted videos
                                    if len(media_bytes) < 1 * 1024 * 1024:  # Less than 1MB
                                        print(f"[DEBUG] ⚠️ Video too small, skipping: {len(media_bytes)} bytes")
                                        continue  # Skip silently to reduce log spam
                                    
                                    print(f"[SUCCESS] 🎥 Found complete video file: {filename}")
                                    media_type = "video"
                                    print(f"[SUCCESS] 📊 Video size: {len(media_bytes)} bytes")
                                    media_found = True
                                    break
                                except Exception as e:
                                    print(f"[ERROR] ❌ Failed to fetch video file: {e}")
                                    continue
                            else:
                                # It's actually an image - but check if this is a video job
                                if model_name and 'wan2' in model_name.lower():
                                    # This is a video job, skip image files
                                    continue  # Skip silently to reduce log spam
                                
                                print(f"[SUCCESS] 🖼️ Found complete image file: {filename}")
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
                        
                # Reduce polling interval when we're close to completion to be more responsive
                if elapsed > 200:  # After 200 seconds, poll more frequently
                    await asyncio.sleep(0.5)  # Poll every 500ms
                else:
                    await asyncio.sleep(1)  # Normal 1 second polling

            # Ensure we're using the correct job ID from the job metadata
            job_id = job.get("id")
            r2_upload_url = job.get("r2_upload")
            
            # For videos, use the R2 upload functionality if available
            if media_type == "video" and r2_upload_url:
                print(f"[UPLOAD] 📤 Uploading video to R2...")
                try:
                    # Upload the video directly to R2 storage with timeout
                    async with httpx.AsyncClient(timeout=30) as client:
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
            
            # Clean up WebSocket task
            websocket_task.cancel()
            try:
                await websocket_task
            except asyncio.CancelledError:
                pass
            
            # Submit result
            print(f"[SUBMIT] 📋 Submitting {media_type} result for job {job_id}")
            await self.api.submit_result(payload)
            print(f"[COMPLETE] ✅ Job {job_id} completed successfully (seed: {payload.get('seed')})")
            
            # Remove job from processing set
            self.processing_jobs.discard(job_id)
            
        except Exception as e:
            # Clean up job from processing set on any error
            self.processing_jobs.discard(job_id)
            # Re-raise the exception so it can be handled by the caller
            raise

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
                
                # Clean up any jobs that might be stuck in processing
                # Note: We can't easily determine which job failed here, so we'll clean up on next cycle
            await asyncio.sleep(2)

    async def listen_comfyui_logs(self, prompt_id: str):
        """Listen to ComfyUI WebSocket for real-time logs and progress"""
        try:
            # Convert http:// to ws:// and https:// to wss://
            ws_url = Settings.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/ws?clientId={prompt_id}"
            
            async with websockets.connect(ws_url) as websocket:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Handle execution start
                        if data.get("type") == "execution_start":
                            print(f"[COMFYUI] got prompt")
                        
                        # Handle progress updates
                        elif data.get("type") == "progress":
                            progress_data = data.get("data", {})
                            current_step = progress_data.get("value", 0)
                            total_steps = progress_data.get("max", 1)
                            node_name = progress_data.get("prompt_id", "")
                            
                            if total_steps > 0:
                                percentage = (current_step / total_steps) * 100
                                print(f"[COMFYUI] {percentage:.0f}%|{'█' * int(percentage/10):<10}| {current_step}/{total_steps} [{node_name}]")
                        
                        # Handle execution error
                        elif data.get("type") == "execution_error":
                            error_data = data.get("data", {})
                            error_msg = error_data.get("exception_message", "Unknown error")
                            print(f"[COMFYUI] ❌ Error: {error_msg}")
                        
                        # Handle execution complete
                        elif data.get("type") == "execution_cached":
                            print(f"[COMFYUI] ✅ Execution completed")
                        
                    except json.JSONDecodeError:
                        # Skip non-JSON messages
                        continue
                    except Exception as e:
                        # Continue on any other errors
                        continue
                        
        except Exception as e:
            # If WebSocket fails, continue without real-time logs
            print(f"[COMFYUI] ⚠️ WebSocket connection failed, using fallback logging")

    async def cleanup(self):
        await self.comfy.aclose()
        await self.api.client.aclose()
