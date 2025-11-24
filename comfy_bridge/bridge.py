import asyncio
import logging
import json
import websockets
from typing import List, Dict, Any, Optional, Set, Callable

from .api_client import APIClient
from .workflow import build_workflow
from .config import Settings
from .model_mapper import initialize_model_mapper, get_horde_models
from .comfyui_client import ComfyUIClient
from .result_processor import ResultProcessor
from .payload_builder import PayloadBuilder
from .job_poller import JobPoller
from .r2_uploader import R2Uploader
from .filesystem_checker import FilesystemChecker

logger = logging.getLogger(__name__)

# Completely disable httpx logging to stop HTTP request spam
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)


class ComfyUIBridge:
    def __init__(
        self,
        api_client: Optional[APIClient] = None,
        comfy_client: Optional[ComfyUIClient] = None,
        workflow_builder: Optional[Callable] = None
    ):
        self.api = api_client or APIClient()
        self.comfy = comfy_client or ComfyUIClient()
        self.workflow_builder = workflow_builder or build_workflow
        
        # Initialize components
        self.result_processor = ResultProcessor(self.comfy)
        self.payload_builder = PayloadBuilder()
        self.job_poller = JobPoller(self.comfy, self.result_processor)
        self.r2_uploader = R2Uploader()
        self.filesystem_checker = FilesystemChecker()
        
        self.supported_models: List[str] = []
        # Track jobs currently being processed to prevent duplicates
        self.processing_jobs: Set[str] = set()
    
    async def process_once(self) -> None:
        """Process a single job from the queue."""
        
        job = await self.api.pop_job(self.supported_models)
        
        # Handle the case where no job is available
        if not job or not job.get("id"):
            return
            
        job_id = job.get("id")
        model_name = job.get('model', 'unknown')
        
        # Check if we're already processing this job (prevent duplicates)
        if job_id in self.processing_jobs:
            logger.warning(f"Job {job_id} already being processed, skipping duplicate")
            return
            
        # Mark job as being processed
        self.processing_jobs.add(job_id)
        logger.info(f"Processing job {job_id} for model {model_name}")
        
        try:
            # Build workflow
            logger.info(f"Building workflow for {model_name}")
            workflow = await self.workflow_builder(job)
            
            # Validate and fix model filenames before submission
            logger.info("Starting model filename validation...")
            validation_failed = False
            try:
                from .workflow import validate_and_fix_model_filenames
                logger.info("Fetching available models from ComfyUI for validation...")
                available_models = await self.comfy.get_available_models()
                logger.info(f"Available models fetched: {list(available_models.keys())} loader types")
                if available_models:
                    logger.info("Validating and fixing model filenames in workflow...")
                    workflow = await validate_and_fix_model_filenames(workflow, available_models)
                    logger.info("Model validation completed")
                else:
                    logger.warning("Could not fetch available models - skipping validation")
            except ImportError as e:
                logger.error(f"Failed to import validate_and_fix_model_filenames: {e}", exc_info=True)
                logger.warning("Proceeding with workflow submission despite validation failure")
            except ValueError as e:
                # ValueError from validation means incompatible models - fail the job
                validation_failed = True
                error_msg = str(e)
                logger.error(f"Model validation failed: {error_msg}")
                logger.error(f"Job {job_id} rejected: Required models are not installed or incompatible")
                # Cancel the job in the API
                try:
                    await self.api.cancel_job(job_id)
                except Exception as cancel_error:
                    logger.error(f"Failed to cancel job {job_id}: {cancel_error}")
                # Raise RuntimeError to prevent workflow submission - this will be caught by outer handler
                raise RuntimeError(f"Job rejected: {error_msg}") from e
            except Exception as e:
                logger.error(f"Model validation failed with unexpected error: {e}", exc_info=True)
                logger.warning("Proceeding with workflow submission despite validation failure")
            
            # Safety check: if validation failed, we should not have reached here
            if validation_failed:
                logger.error("CRITICAL: Validation failed but execution continued - this should not happen!")
                raise RuntimeError("Validation failed but execution continued unexpectedly")
            
            # Submit workflow to ComfyUI
            prompt_id = await self.comfy.submit_workflow(workflow)
            
            # Start WebSocket listener for ComfyUI logs
            websocket_task = asyncio.create_task(self.listen_comfyui_logs(prompt_id))
            
            # Poll for completion with filesystem fallback
            async def filesystem_checker(jid: str):
                return await self.filesystem_checker.check_for_completed_file(jid)
            
            media_bytes, media_type, filename = await self.job_poller.poll_until_complete(
                prompt_id, job_id, model_name, filesystem_checker
            )
            
            # Handle R2 upload for videos if available
            r2_upload_url = job.get("r2_upload")
            if media_type == "video" and r2_upload_url:
                logger.info("Uploading video to R2...")
                await self.r2_uploader.upload_video(r2_upload_url, media_bytes)
            
            # Build and submit payload
            payload = self.payload_builder.build_payload(
                job, media_bytes, media_type, filename
            )
            
            # Clean up WebSocket task
            websocket_task.cancel()
            try:
                await websocket_task
            except asyncio.CancelledError:
                pass
            
            # Submit result
            logger.info(f"Submitting {media_type} result for job {job_id}")
            await self.api.submit_result(payload)
            logger.info(f"Job {job_id} completed successfully (seed: {payload.get('seed')})")
            
            # Remove job from processing set
            self.processing_jobs.discard(job_id)
            
        except Exception as e:
            # Clean up job from processing set on any error
            self.processing_jobs.discard(job_id)
            
            # Cancel the job in the API to prevent other workers from picking it up
            try:
                await self.api.cancel_job(job_id)
            except Exception as cancel_error:
                logger.error(f"Failed to cancel job {job_id}: {cancel_error}")
            
            # Re-raise the exception so it can be handled by the caller
            raise

    async def run(self):
        logger.info("ComfyUI Bridge starting...")
        logger.info(f"ComfyUI: {Settings.COMFYUI_URL}")
        logger.info(f"AI Power Grid: {Settings.GRID_API_URL}")
        logger.info(f"Worker: {Settings.GRID_WORKER_NAME}")
        if Settings.DEBUG:
            logger.info("DEBUG MODE ENABLED - Detailed logging active")
        
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prioritize WORKFLOW_FILE when set, otherwise use auto-detected models
        derived_models = get_horde_models()
        if Settings.GRID_MODELS:
            # WORKFLOW_FILE is explicitly set - use the resolved models from the mapper
            self.supported_models = derived_models
            logger.info(f"Using models from WORKFLOW_FILE: {Settings.GRID_MODELS}")
            if not self.supported_models:
                logger.warning("No models resolved from WORKFLOW_FILE!")
        elif Settings.WORKFLOW_FILE:
            # WORKFLOW_FILE is set - use auto-detected models
            self.supported_models = derived_models
            if not self.supported_models:
                logger.warning("No models resolved from WORKFLOW_FILE!")
        else:
            # Fallback to auto-detected models
            if derived_models:
                self.supported_models = derived_models
            else:
                self.supported_models = []
                
        logger.info(f"Advertising {len(self.supported_models)} models:")
        for i, model in enumerate(self.supported_models, 1):
            logger.info(f"  {i}. {model}")
            
        if not self.supported_models:
            logger.error("CRITICAL: No models configured! The bridge will not receive any jobs.")
            logger.error("To fix this, either:")
            logger.error("  1. Set WORKFLOW_FILE in your .env file, or") 
            logger.error("  2. Ensure DEFAULT_WORKFLOW_MAP contains models")

        job_count = 0
        while True:
            job_count += 1
            # Only show polling message every 10 attempts to reduce noise
            if job_count % 10 == 1:
                logger.debug(f"Service running (poll #{job_count})")
            try:
                await self.process_once()
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=Settings.DEBUG)
                
                # Clean up any jobs that might be stuck in processing
                # Note: We can't easily determine which job failed here, so we'll clean up on next cycle
            await asyncio.sleep(2)

    async def listen_comfyui_logs(self, prompt_id: str):
        """Listen to ComfyUI WebSocket for real-time logs and progress"""
        try:
            # Convert http:// to ws:// and https:// to wss://
            ws_url = Settings.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/ws?clientId={prompt_id}"
            
            logger.debug(f"Connecting to ComfyUI WebSocket: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                logger.debug("WebSocket connected, waiting for messages...")
                message_count = 0
                async for message in websocket:
                    message_count += 1
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        # Handle execution start
                        if msg_type == "execution_start":
                            logger.info(f"Execution started (prompt: {prompt_id})")
                        
                        # Handle execution queued
                        elif msg_type == "status":
                            status_data = data.get("data", {})
                            queue_remaining = status_data.get("status", {}).get("exec_info", {}).get("queue_remaining", 0)
                            if queue_remaining > 0:
                                logger.info(f"Queue status: {queue_remaining} jobs ahead")
                        
                        # Handle progress updates
                        elif msg_type == "progress":
                            progress_data = data.get("data", {})
                            current_step = progress_data.get("value", 0)
                            total_steps = progress_data.get("max", 1)
                            node = progress_data.get("node", "")
                            
                            if total_steps > 0:
                                percentage = (current_step / total_steps) * 100
                                logger.info(f"Progress: {percentage:.0f}% ({current_step}/{total_steps}) [node:{node}]")
                        
                        # Handle node execution
                        elif msg_type == "executing":
                            node_id = data.get("data", {}).get("node")
                            if node_id:
                                logger.debug(f"Executing node: {node_id}")
                            else:
                                logger.info("Workflow execution complete")
                        
                        # Handle execution error
                        elif msg_type == "execution_error":
                            error_data = data.get("data", {})
                            error_msg = error_data.get("exception_message", "Unknown error")
                            node_id = error_data.get("node_id", "unknown")
                            node_type = error_data.get("node_type", "unknown")
                            logger.error(f"Error in node {node_id} ({node_type}): {error_msg}")
                            if Settings.DEBUG:
                                logger.debug(f"Full error data: {error_data}")
                        
                        # Handle execution interrupted
                        elif msg_type == "execution_interrupted":
                            logger.warning("Execution interrupted")
                        
                        # Handle execution cached
                        elif msg_type == "execution_cached":
                            cached_nodes = data.get("data", {}).get("nodes", [])
                            if Settings.DEBUG:
                                logger.debug(f"Cached nodes: {cached_nodes}")
                        
                        # Handle progress_state (detailed node progress)
                        elif msg_type == "progress_state" and Settings.DEBUG:
                            progress_data = data.get("data", {})
                            nodes = progress_data.get("nodes", {})
                            running = [nid for nid, ndata in nodes.items() if ndata.get("state") == "running"]
                            
                            if running:
                                for node_id in running:
                                    node_data = nodes[node_id]
                                    val = node_data.get("value", 0)
                                    max_val = node_data.get("max", 1)
                                    if max_val > 1:
                                        pct = (val / max_val) * 100
                                        logger.debug(f"Node {node_id}: {pct:.0f}% ({val}/{max_val})")
                        
                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON WebSocket message: {message[:100]}")
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing WS message: {e}")
                        continue
                        
        except Exception as e:
            # If WebSocket fails, continue without real-time logs
            logger.warning(f"WebSocket connection failed: {e}")
            if Settings.DEBUG:
                logger.debug("WebSocket error", exc_info=True)

    async def cleanup(self):
        await self.comfy.close()
        if hasattr(self.api, 'client'):
            await self.api.client.aclose()
