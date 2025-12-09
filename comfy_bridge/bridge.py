import asyncio
import logging
import json
import websockets  # type: ignore  # websockets installed via requirements.txt in Docker
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
from .optional_deps import check_optional_dependencies
from .modelvault_client import get_modelvault_client, ModelVaultClient
from .health import get_health_checker, validate_job_for_model, ModelHealthChecker

logger = logging.getLogger(__name__)

# Completely disable httpx logging to stop HTTP request spam
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)


class ComfyUIBridge:
    def __init__(
        self,
        api_client: Optional[APIClient] = None,
        comfy_client: Optional[ComfyUIClient] = None,
        workflow_builder: Optional[Callable] = None,
        modelvault_enabled: bool = True
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
        
        # Initialize ModelVault client for on-chain validation
        modelvault_enabled = modelvault_enabled and Settings.MODELVAULT_ENABLED
        self.modelvault: ModelVaultClient = get_modelvault_client(enabled=modelvault_enabled)
        
        # Initialize health checker for model file validation
        self.health_checker: ModelHealthChecker = get_health_checker()

        # Check optional dependencies
        check_optional_dependencies()

        self.supported_models: List[str] = []
        # Track jobs currently being processed to prevent duplicates
        self.processing_jobs: Set[str] = set()
        # Track models that have failed validation (don't advertise)
        self.unhealthy_models: Set[str] = set()
    
    async def process_once(self) -> None:
        """Process a single job from the queue."""
        
        job = await self.api.pop_job(self.supported_models)
        
        # Handle the case where no job is available
        if not job or not job.get("id"):
            logger.debug(f"No job available (response: {job})")
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
            # Health check: validate model files exist before accepting job
            can_serve, health_reason = validate_job_for_model(model_name)
            if not can_serve:
                logger.error(f"❌ Rejecting job {job_id}: {health_reason}")
                # Track unhealthy model to potentially remove from advertising
                self.unhealthy_models.add(model_name)
                try:
                    await self.api.cancel_job(job_id)
                    logger.info(f"Cancelled job {job_id} due to model health check failure")
                except Exception as cancel_error:
                    logger.error(f"Failed to cancel job {job_id}: {cancel_error}")
                self.processing_jobs.discard(job_id)
                return
            
            # On-chain model validation (if enabled)
            if self.modelvault.enabled:
                steps = job.get("params", {}).get("steps", 20)
                cfg = job.get("params", {}).get("cfg_scale", 7.0)
                sampler = job.get("params", {}).get("sampler_name")
                scheduler = job.get("params", {}).get("scheduler")
                
                validation = self.modelvault.validate_params(
                    file_name=model_name,
                    steps=steps,
                    cfg=cfg,
                    sampler=sampler,
                    scheduler=scheduler,
                )
                
                if not validation.is_valid:
                    logger.warning(f"ModelVault validation failed: {validation.reason}")
                    # Cancel job with validation failure
                    try:
                        await self.api.cancel_job(job_id)
                    except Exception as cancel_error:
                        logger.error(f"Failed to cancel job {job_id}: {cancel_error}")
                    self.processing_jobs.discard(job_id)
                    return

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
                await self.r2_uploader.upload_video(r2_upload_url, media_bytes, filename, media_type)
            
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
            if Settings.DEBUG:
                await self._log_post_submit_status(job_id)
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
        if self.modelvault.enabled:
            logger.info(f"ModelVault: Enabled (Base Sepolia)")
            active_models = self.modelvault.get_all_active_models()
            logger.info(f"  {len(active_models)} models registered on-chain")
        else:
            logger.info("ModelVault: Disabled (web3 not installed or connection failed)")
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
                
        # Health check: validate model files exist before advertising
        self.health_checker.set_advertised_models(self.supported_models)
        worker_health = self.health_checker.get_worker_health()
        
        # Filter to only advertise healthy/servable models
        healthy_models = worker_health.servable_models
        unhealthy = set(self.supported_models) - set(healthy_models)
        
        if unhealthy:
            logger.warning(f"⚠️  {len(unhealthy)} models have missing files and won't be advertised:")
            for model in unhealthy:
                health = worker_health.model_details.get(model)
                if health:
                    logger.warning(f"    ✗ {model}: {health.error_message}")
                    if health.missing_files:
                        for f in health.missing_files[:3]:
                            logger.warning(f"        Missing: {f}")
        
        # Only advertise healthy models
        self.supported_models = healthy_models
        
        logger.info(f"Advertising {len(self.supported_models)} healthy models:")
        for i, model in enumerate(self.supported_models, 1):
            health = worker_health.model_details.get(model)
            status = "✓" if health and health.is_healthy else "~"
            logger.info(f"  {i}. {status} {model}")
            
        if not self.supported_models:
            logger.error("CRITICAL: No healthy models to advertise! The bridge will not receive any jobs.")
            logger.error("To fix this, either:")
            logger.error("  1. Download the model files, or") 
            logger.error("  2. Check WORKFLOW_FILE configuration")

        job_count = 0
        logger.info("Starting job polling loop...")
        while True:
            job_count += 1
            # Show polling message every 15 attempts (every ~30 seconds)
            if job_count % 15 == 1:
                logger.info(f"👀 Polling for jobs... (poll #{job_count}, models: {len(self.supported_models)})")
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

    async def _log_post_submit_status(self, job_id: str) -> None:
        """Fetch and log Horde status immediately after submitting a payload."""
        try:
            status_payload = await self.api.get_request_status(job_id)
        except Exception as exc:
            logger.debug("Post-submit status fetch failed for job %s: %s", job_id, exc)
            return

        generations = status_payload.get("generations") or []
        state = (
            status_payload.get("state")
            or status_payload.get("status", {}).get("status_str")
            or status_payload.get("status", {}).get("state")
        )

        logger.debug(
            "Post-submit Horde status for job %s: state=%s, kudos=%s, generations=%s",
            job_id,
            state,
            status_payload.get("kudos") or status_payload.get("kudos_consumed"),
            len(generations),
        )

        if generations:
            sample = generations[0]
            logger.debug(
                "First generation metadata: media_type=%s form=%s type=%s keys=%s",
                sample.get("media_type"),
                sample.get("form"),
                sample.get("type"),
                list(sample.keys()),
            )
