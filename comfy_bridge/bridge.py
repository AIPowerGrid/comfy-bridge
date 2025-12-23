import asyncio
import logging
import json
import websockets  # type: ignore  # websockets installed via requirements.txt in Docker
from typing import List, Dict, Any, Optional, Set, Callable

from .api_client import APIClient
from .workflow import build_workflow, detect_workflow_model_type, is_model_compatible
from .config import Settings
from .model_mapper import initialize_model_mapper, get_horde_models, get_workflow_file
from .comfyui_client import ComfyUIClient
import os
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
    
    async def process_once(self) -> bool:
        """Process a single job from the queue. Returns True if a job was processed."""
        
        job = await self.api.pop_job(self.supported_models)
        
        # Handle the case where no job is available
        if not job or not job.get("id"):
            logger.debug(f"No job available (response: {job})")
            return False
            
        job_id = job.get("id")
        model_name = job.get('model', 'unknown')
        
        # DEBUG: Log exact job model received vs what we advertise
        logger.info(f"📥 JOB RECEIVED: id={job_id}, model='{model_name}'")
        logger.info(f"   Job model in our list? {model_name in self.supported_models}")
        if model_name not in self.supported_models:
            logger.warning(f"⚠️ MISMATCH: Job model '{model_name}' not in our advertised list: {self.supported_models}")
        
        # Check if we're already processing this job (prevent duplicates)
        if job_id in self.processing_jobs:
            logger.warning(f"Job {job_id} already being processed, skipping duplicate")
            return False
            
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
                return False
            
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
                    return False

            # Build workflow
            logger.info(f"Building workflow for {model_name}")
            workflow = await self.workflow_builder(job)
            
            # DEBUG: Log workflow RIGHT AFTER BUILD
            logger.info(f"DEBUG AFTER BUILD - Node 45 text: {workflow.get('45', {}).get('inputs', {}).get('text', 'NOT FOUND')[:100]}")
            logger.info(f"DEBUG AFTER BUILD - Node 31 seed: {workflow.get('31', {}).get('inputs', {}).get('seed', 'NOT FOUND')}")
            logger.info(f"DEBUG AFTER BUILD - Node 40 clip_name2: {workflow.get('40', {}).get('inputs', {}).get('clip_name2', 'NOT FOUND')}")
            
            # Validate WanVideo workflow parameters before submission
            try:
                from .workflow import validate_wanvideo_workflow
                validate_wanvideo_workflow(workflow)
            except ImportError:
                pass  # Function may not exist in older versions
            except Exception as e:
                logger.warning(f"WanVideo workflow validation warning: {e}")
            
            # Validate and fix model filenames before submission
            logger.info("Starting model filename validation...")
            validation_failed = False
            
            # DEBUG: Log workflow BEFORE validation
            logger.info(f"DEBUG BEFORE VALIDATION - Node 45 text: {workflow.get('45', {}).get('inputs', {}).get('text', 'NOT FOUND')[:100]}")
            logger.info(f"DEBUG BEFORE VALIDATION - Node 31 seed: {workflow.get('31', {}).get('inputs', {}).get('seed', 'NOT FOUND')}")
            
            try:
                from .workflow import validate_and_fix_model_filenames
                logger.info("Fetching available models from ComfyUI for validation...")
                available_models = await self.comfy.get_available_models()
                logger.info(f"Available models fetched: {list(available_models.keys())} loader types")
                if available_models:
                    logger.info("Validating and fixing model filenames in workflow...")
                    workflow = await validate_and_fix_model_filenames(workflow, available_models, job_model_name=model_name)
                    logger.info("Model validation completed")
                    
                    # DEBUG: Log workflow AFTER validation
                    logger.info(f"DEBUG AFTER VALIDATION - Node 45 text: {workflow.get('45', {}).get('inputs', {}).get('text', 'NOT FOUND')[:100]}")
                    logger.info(f"DEBUG AFTER VALIDATION - Node 31 seed: {workflow.get('31', {}).get('inputs', {}).get('seed', 'NOT FOUND')}")
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
            
            # Start WebSocket listener for ComfyUI logs (with job_id for progress reporting)
            websocket_task = asyncio.create_task(self.listen_comfyui_logs(prompt_id, job_id))
            
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
            return True
            
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
            logger.info(f"ModelVault: Enabled (Base Mainnet)")
            active_models = self.modelvault.get_all_active_models()
            logger.info(f"  {len(active_models)} models registered on-chain")
        else:
            logger.info("ModelVault: Disabled (web3 not installed or connection failed)")
        if Settings.DEBUG:
            logger.info("DEBUG MODE ENABLED - Detailed logging active")
        
        await initialize_model_mapper(Settings.COMFYUI_URL)

        # Prioritize WORKFLOW_FILE when set, otherwise use auto-detected models
        derived_models = get_horde_models()
        logger.info(f"🔧 Config:")
        logger.info(f"   WORKFLOW_FILE env: {Settings.WORKFLOW_FILE}")
        logger.info(f"   GRID_MODELS (raw): {Settings.GRID_MODELS}")
        logger.info(f"   get_horde_models() returned: {derived_models}")
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
        
        # Additional validation: cross-check against ComfyUI's available models
        # This catches cases where files exist but ComfyUI can't load them
        try:
            available_models = await self.comfy.get_available_models()
            
            # Validate each healthy model against ComfyUI's available loaders
            comfyui_validated = []
            for model_name in healthy_models:
                try:
                    workflow_file = get_workflow_file(model_name)
                    workflow_path = os.path.join(Settings.WORKFLOW_DIR, workflow_file)
                    
                    if os.path.exists(workflow_path):
                        with open(workflow_path, 'r') as f:
                            workflow = json.load(f)
                        
                        model_type = detect_workflow_model_type(workflow)
                        
                        # Check if required loaders have compatible models available
                        can_serve = True
                        if model_type == "flux":
                            unet_models = available_models.get("UNETLoader", [])
                            dual_clip = available_models.get("DualCLIPLoader", {})
                            vae_models = available_models.get("VAELoader", [])
                            
                            flux_unet = [m for m in unet_models if is_model_compatible(m, "flux")]
                            clip1 = dual_clip.get("clip_name1", []) if isinstance(dual_clip, dict) else []
                            clip2 = dual_clip.get("clip_name2", []) if isinstance(dual_clip, dict) else []
                            flux_clip1 = [m for m in clip1 if is_model_compatible(m, "flux")]
                            flux_clip2 = [m for m in clip2 if is_model_compatible(m, "flux")]
                            flux_vae = [m for m in vae_models if is_model_compatible(m, "flux")]
                            
                            if not flux_unet or not (flux_clip1 or flux_clip2) or not flux_vae:
                                can_serve = False
                                logger.warning(f"    ✗ {model_name}: Flux models not available in ComfyUI (UNET: {len(flux_unet)}, CLIP: {len(flux_clip1 + flux_clip2)}, VAE: {len(flux_vae)})")
                        elif model_type == "sdxl":
                            checkpoints = available_models.get("checkpoints", []) or available_models.get("CheckpointLoaderSimple", [])
                            if not checkpoints:
                                can_serve = False
                                logger.warning(f"    ✗ {model_name}: No checkpoint models available in ComfyUI")
                        elif model_type == "wanvideo":
                            # WanVideo models use custom loaders - if workflow exists and health check passed, trust it
                            # The health checker already validated file existence
                            can_serve = True
                        elif model_type == "unknown":
                            # Unknown model type - if health check passed, trust it
                            # This handles edge cases and new model types
                            can_serve = True
                        else:
                            # Other model types - if health check passed, trust it
                            can_serve = True
                        
                        if can_serve:
                            comfyui_validated.append(model_name)
                    else:
                        # Workflow file missing - shouldn't happen but handle gracefully
                        logger.warning(f"    ✗ {model_name}: Workflow file not found: {workflow_path}")
                except Exception as e:
                    logger.warning(f"    ✗ {model_name}: Error validating against ComfyUI: {e}")
                    # On error, include the model to be safe (might be a transient issue)
                    comfyui_validated.append(model_name)
            
            # Update supported models to only include ComfyUI-validated ones
            comfyui_invalid = set(healthy_models) - set(comfyui_validated)
            if comfyui_invalid:
                logger.warning(f"⚠️  {len(comfyui_invalid)} models filtered out (not available in ComfyUI): {list(comfyui_invalid)}")
            
            # Only use ComfyUI validation if we got some results - otherwise fall back to health checker
            if comfyui_validated:
                self.supported_models = comfyui_validated
                logger.info(f"✅ ComfyUI validation: {len(comfyui_validated)} models validated")
            else:
                logger.warning("⚠️  ComfyUI validation filtered out all models - falling back to health checker results")
                self.supported_models = healthy_models
        except Exception as e:
            logger.error(f"Failed to validate models against ComfyUI: {e}", exc_info=True)
            logger.warning("Falling back to health checker results only")
            # Fallback to health checker results if ComfyUI validation fails
            self.supported_models = healthy_models
        
        logger.info(f"🚀 ADVERTISING {len(self.supported_models)} healthy models to Grid API:")
        for i, model in enumerate(self.supported_models, 1):
            health = worker_health.model_details.get(model)
            status = "✓" if health and health.is_healthy else "~"
            logger.info(f"  {i}. {status} '{model}'")
        
        # Log the exact model names being sent to API (helps debug case-sensitivity issues)
        logger.info(f"📋 EXACT MODEL NAMES: {self.supported_models}")
            
        if not self.supported_models:
            logger.error("CRITICAL: No healthy models to advertise! The bridge will not receive any jobs.")
            logger.error("To fix this, either:")
            logger.error("  1. Download the model files, or") 
            logger.error("  2. Check WORKFLOW_FILE configuration")

        # Check what models have jobs in the queue
        try:
            logger.info("🔍 Checking API queue status...")
            models_status = await self.api.get_models_status()
            if models_status:
                # Find models with queued jobs
                models_with_jobs = []
                for model_info in models_status:
                    if isinstance(model_info, dict):
                        name = model_info.get("name", "")
                        queued = model_info.get("queued", 0)
                        if queued > 0:
                            models_with_jobs.append((name, queued))
                
                if models_with_jobs:
                    logger.info(f"📊 Models with queued jobs in API:")
                    for name, queued in sorted(models_with_jobs, key=lambda x: -x[1])[:20]:
                        # Check if we support this model
                        supported = "✓" if name in self.supported_models else "✗"
                        logger.info(f"   {supported} {name}: {queued} jobs")
                    
                    # Check for matches
                    our_models_set = set(self.supported_models)
                    queue_models_set = set(name for name, _ in models_with_jobs)
                    matching = our_models_set & queue_models_set
                    if matching:
                        logger.info(f"✅ We can serve {len(matching)} models with queued jobs: {list(matching)}")
                    else:
                        logger.warning("⚠️  NONE of our models have queued jobs!")
                        logger.warning(f"   Our models: {self.supported_models}")
                        logger.warning(f"   Models with jobs: {[n for n, _ in models_with_jobs[:10]]}")
                else:
                    logger.info("📭 No models have queued jobs right now")
            else:
                logger.warning("Could not fetch models status from API")
        except Exception as e:
            logger.warning(f"Failed to check queue status: {e}")

        job_count = 0
        last_queue_check = 0
        logger.info("Starting job polling loop...")
        while True:
            job_count += 1
            # Show polling message every 15 attempts (every ~30 seconds)
            if job_count % 15 == 1:
                logger.info(f"👀 Polling for jobs... (poll #{job_count}, models: {len(self.supported_models)})")
            
            # Periodically check which models have jobs (every 100 polls)
            if job_count - last_queue_check >= 100:
                last_queue_check = job_count
                try:
                    models_status = await self.api.get_models_status()
                    if models_status:
                        models_with_jobs = []
                        for model_info in models_status:
                            if isinstance(model_info, dict):
                                name = model_info.get("name", "")
                                queued = model_info.get("queued", 0)
                                if queued > 0:
                                    models_with_jobs.append((name, queued))
                        
                        if models_with_jobs:
                            logger.info(f"📊 Models with queued jobs (poll #{job_count}):")
                            for name, queued in sorted(models_with_jobs, key=lambda x: -x[1])[:10]:
                                supported = "✓" if name in self.supported_models else "✗"
                                logger.info(f"   {supported} {name}: {queued} jobs")
                except Exception as e:
                    logger.debug(f"Could not check queue status: {e}")
            
            try:
                job_received = await self.process_once()
                # If we got a job, poll again immediately for more work
                if job_received:
                    continue
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=Settings.DEBUG)
                
                # Clean up any jobs that might be stuck in processing
                # Note: We can't easily determine which job failed here, so we'll clean up on next cycle
            
            # No job received - wait before next poll (shorter interval for faster pickup)
            await asyncio.sleep(1.0)

    async def listen_comfyui_logs(self, prompt_id: str, job_id: str = None):
        """Listen to ComfyUI WebSocket for real-time logs and progress.
        
        Args:
            prompt_id: The ComfyUI prompt ID
            job_id: The API job ID (for reporting progress to the API)
        """
        # Track last progress update to avoid spamming the API
        last_progress_update = 0
        progress_update_interval = 2.0  # Update API every 2 seconds max
        
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
                                if queue_remaining == 1:
                                    logger.info(f"Queue status: Our job is queued (1 job in queue)")
                                else:
                                    logger.info(f"Queue status: {queue_remaining - 1} jobs ahead of ours ({queue_remaining} total in queue)")
                        
                        # Handle progress updates
                        elif msg_type == "progress":
                            progress_data = data.get("data", {})
                            current_step = progress_data.get("value", 0)
                            total_steps = progress_data.get("max", 1)
                            node = progress_data.get("node", "")
                            
                            if total_steps > 0:
                                percentage = (current_step / total_steps) * 100
                                logger.info(f"Progress: {percentage:.0f}% ({current_step}/{total_steps}) [node:{node}]")
                                
                                # Report progress to the API (throttled)
                                import time
                                now = time.time()
                                if job_id and (now - last_progress_update) >= progress_update_interval:
                                    last_progress_update = now
                                    # Fire and forget - don't await to avoid blocking
                                    asyncio.create_task(
                                        self.api.update_progress(job_id, current_step, total_steps)
                                    )
                        
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
