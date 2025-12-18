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
        max_wait_time: int = 1800,
        filesystem_fallback_time: int = 300
    ):
        self.comfy = comfy_client
        self.result_processor = result_processor
        self.max_wait_time = max_wait_time
        self.filesystem_fallback_time = filesystem_fallback_time
        self._filesystem_checked = False
    
    async def poll_until_complete(
        self, prompt_id: str, job_id: str, model_name: str,
        filesystem_checker: Optional[callable] = None
    ) -> Tuple[bytes, str, str]:
        start_time = time.time()
        last_progress_time = start_time
        self._filesystem_checked = False
        
        while True:
            elapsed = time.time() - start_time
            
            # Show progress periodically
            if not Settings.DEBUG and int(elapsed) % 30 == 0 and int(elapsed) > 0:
                logger.info(f"Processing... ({elapsed:.0f}s)")
            
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
            
            if status.get("completed", False):
                if not outputs:
                    raise Exception("Workflow completed without outputs")
                
                result = await self.result_processor.process_outputs(outputs, model_name)
                if result:
                    return result
            
            # Fast polling interval for responsive progress updates
            await asyncio.sleep(0.3)
    
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

