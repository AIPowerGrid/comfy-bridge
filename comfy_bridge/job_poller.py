import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple
from .config import Settings

logger = logging.getLogger(__name__)


class JobPoller:
    def __init__(
        self,
        comfy_client,
        result_processor,
        max_wait_time: int = 7200,  # 2 hours (4x increase for video support)
        filesystem_fallback_time: int = 1200,  # 20 minutes (4x increase for video)
        stuck_detection_time: int = 120  # 2 minutes before checking if stuck
    ):
        self.comfy = comfy_client
        self.result_processor = result_processor
        self.max_wait_time = max_wait_time
        self.filesystem_fallback_time = filesystem_fallback_time
        self.stuck_detection_time = stuck_detection_time
        self._filesystem_checked = False
        self._last_queue_check = 0
        self._queue_check_interval = 30  # Check queue every 30 seconds
        self._no_progress_since = None  # Track when we last saw progress
    
    async def poll_until_complete(
        self, prompt_id: str, job_id: str, model_name: str,
        filesystem_checker: Optional[callable] = None
    ) -> Tuple[bytes, str, str]:
        start_time = time.time()
        last_progress_time = start_time
        self._filesystem_checked = False
        self._no_progress_since = None
        last_status_str = None
        
        while True:
            elapsed = time.time() - start_time
            now = time.time()
            
            # Check for max wait time exceeded
            if elapsed > self.max_wait_time:
                logger.error(f"Job {job_id} exceeded max wait time ({self.max_wait_time}s)")
                raise Exception(f"Job timed out after {elapsed:.0f}s")
            
            # Show progress periodically
            if not Settings.DEBUG and int(elapsed) % 30 == 0 and int(elapsed) > 0:
                logger.info(f"Processing... ({elapsed:.0f}s)")
            
            # Periodically check ComfyUI queue status to detect stuck jobs
            if now - self._last_queue_check > self._queue_check_interval:
                self._last_queue_check = now
                await self._check_queue_health(prompt_id, job_id, elapsed)
            
            # Check filesystem fallback if configured
            if (filesystem_checker and 
                elapsed > self.filesystem_fallback_time and 
                not self._filesystem_checked):
                self._filesystem_checked = True
                logger.debug("Checking filesystem fallback...")
                result = await filesystem_checker(job_id)
                if result:
                    return result
            
            # Get job status
            data = await self.comfy.get_history(prompt_id)
            
            # Debug logging
            if Settings.DEBUG and (elapsed - last_progress_time) > 10:
                last_progress_time = elapsed
                status = data.get("status", {})
                outputs = data.get("outputs", {})
                logger.debug(
                    f"Polling: completed={status.get('completed', False)}, "
                    f"has_outputs={len(outputs) > 0}, elapsed={elapsed:.1f}s"
                )
            
            # Check for errors
            self._check_for_errors(data)
            
            # Check for completion
            status = data.get("status", {})
            outputs = data.get("outputs", {})
            
            # Track if we're seeing any status changes (progress detection)
            current_status_str = str(status)
            if current_status_str != last_status_str:
                last_status_str = current_status_str
                self._no_progress_since = None  # Reset - we're seeing changes
            elif self._no_progress_since is None:
                self._no_progress_since = now  # Start tracking stall
            
            # Check for stuck job (no progress for too long)
            if self._no_progress_since and (now - self._no_progress_since) > self.stuck_detection_time:
                logger.warning(
                    f"⚠️  Job {job_id} appears stuck - no status change for "
                    f"{now - self._no_progress_since:.0f}s. Checking queue..."
                )
                await self._diagnose_stuck_job(prompt_id, job_id, elapsed)
                # Reset to avoid spamming
                self._no_progress_since = now
            
            if status.get("completed", False):
                if not outputs:
                    raise Exception("Workflow completed without outputs")
                
                result = await self.result_processor.process_outputs(outputs, model_name)
                if result:
                    return result
            
            # Fast polling interval for responsive progress updates
            await asyncio.sleep(0.3)
    
    async def _check_queue_health(self, prompt_id: str, job_id: str, elapsed: float) -> None:
        """Check ComfyUI queue status to detect issues."""
        try:
            queue = await self.comfy.get_queue()
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            
            # Find our job in the queue
            our_job_running = any(p[1] == prompt_id for p in running) if running else False
            our_job_pending = any(p[1] == prompt_id for p in pending) if pending else False
            
            if running:
                running_ids = [p[1] for p in running]
                if our_job_running:
                    logger.debug(f"Queue check: Our job is running (elapsed: {elapsed:.0f}s)")
                else:
                    logger.info(f"Queue check: {len(running)} jobs running, ours pending. Running: {running_ids[:3]}")
            elif pending:
                pending_ids = [p[1] for p in pending]
                if our_job_pending:
                    logger.warning(
                        f"⚠️  Queue check: Our job {prompt_id[:8]}... is pending but nothing is running! "
                        f"({len(pending)} jobs pending, elapsed: {elapsed:.0f}s)"
                    )
                else:
                    logger.warning(
                        f"⚠️  Queue check: {len(pending)} jobs pending but ours not found! "
                        f"Pending: {[p[:8] for p in pending_ids[:3]]}"
                    )
            else:
                # Queue is empty - job might have errored silently
                logger.warning(
                    f"⚠️  Queue is empty but job {job_id} not complete (elapsed: {elapsed:.0f}s)"
                )
        except Exception as e:
            logger.debug(f"Queue health check failed: {e}")
    
    async def _diagnose_stuck_job(self, prompt_id: str, job_id: str, elapsed: float) -> None:
        """Diagnose why a job might be stuck."""
        try:
            # Check queue
            queue = await self.comfy.get_queue()
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            
            logger.info(f"🔍 Diagnosing stuck job {job_id}:")
            logger.info(f"   Queue: {len(running)} running, {len(pending)} pending")
            
            # Check system stats
            stats = await self.comfy.get_system_stats()
            if stats:
                devices = stats.get("devices", [])
                for i, device in enumerate(devices):
                    name = device.get("name", f"Device {i}")
                    vram_total = device.get("vram_total", 0)
                    vram_free = device.get("vram_free", 0)
                    if vram_total > 0:
                        vram_used_pct = ((vram_total - vram_free) / vram_total) * 100
                        logger.info(f"   GPU {i} ({name}): {vram_used_pct:.1f}% VRAM used")
            
            # Check if our job is in the queue
            our_running = any(p[1] == prompt_id for p in running) if running else False
            our_pending = any(p[1] == prompt_id for p in pending) if pending else False
            
            if our_running:
                logger.info("   Status: Our job IS running in ComfyUI (may be slow/large model)")
            elif our_pending:
                logger.warning("   Status: Our job is PENDING but nothing is running!")
                logger.warning("   → ComfyUI execution may be stuck. Consider restarting ComfyUI.")
            elif not running and not pending:
                logger.warning("   Status: Queue is EMPTY - job may have failed silently")
                logger.warning("   → Check ComfyUI logs for errors")
            else:
                logger.warning(f"   Status: Other jobs in queue, ours not found")
                logger.warning(f"   → Job may have been lost. Running: {[p[1][:8] for p in running[:3]]}")
            
        except Exception as e:
            logger.error(f"Failed to diagnose stuck job: {e}")
    
    def _check_for_errors(self, data: Dict[str, Any]) -> None:
        status = data.get("status", {})
        status_str = status.get("status_str", "")
        
        if status_str == "error":
            error_msg = self._extract_error_message(status)
            logger.error(f"ComfyUI workflow failed: {error_msg}")
            
            # Log additional context for WanVideoDecode errors
            if "WanVideoDecode" in error_msg and "tensor" in error_msg.lower():
                logger.error(
                    "WanVideoDecode tensor dimension error detected. "
                    "This usually indicates a mismatch between WanVideoDecode tile_x/tile_y "
                    "and the WanVideoSampler output dimensions. "
                    "Check the workflow file's tile parameters match the model's expected dimensions."
                )
            
            if Settings.DEBUG:
                logger.debug(f"Full status data: {status}")
            raise Exception(f"ComfyUI workflow failed: {error_msg}")
    
    def _extract_error_message(self, status: Dict[str, Any]) -> str:
        messages = status.get("messages", [])
        
        for msg in messages:
            if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
                error_data = msg[1] if isinstance(msg[1], dict) else {}
                error_msg = error_data.get("exception_message", "Unknown execution error")
                node_id = error_data.get("node_id", "unknown")
                node_type = error_data.get("node_type", "unknown")
                
                # Add helpful context for WanVideoDecode tensor dimension errors
                if node_type == "WanVideoDecode" and "tensor" in error_msg.lower() and "size" in error_msg.lower():
                    enhanced_msg = (
                        f"{error_msg}\n"
                        f"This error typically occurs when WanVideoDecode tile_x/tile_y parameters "
                        f"don't match the WanVideoSampler output tensor dimensions. "
                        f"Check that the workflow's tile_x/tile_y values are compatible with "
                        f"the WanVideoEmptyEmbeds width/height/num_frames settings."
                    )
                    return f"Node {node_id} ({node_type}): {enhanced_msg}"
                
                return f"Node {node_id} ({node_type}): {error_msg}"
        
        return status.get("exception_message", "Unknown execution error")

