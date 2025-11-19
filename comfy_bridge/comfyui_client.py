import logging
import httpx
from typing import Dict, Any
from .config import Settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    def __init__(self, base_url: str = None, timeout: int = 300):
        self.base_url = base_url or Settings.COMFYUI_URL
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
    
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        logger.debug(f"Submitting workflow to ComfyUI ({len(workflow)} nodes)")
        
        resp = await self.client.post("/prompt", json={"prompt": workflow})
        if resp.status_code != 200:
            error_text = resp.text
            logger.error(f"ComfyUI error response (status {resp.status_code}): {error_text}")
            try:
                error_json = resp.json()
                logger.error(f"ComfyUI error JSON: {error_json}")
                # Log node errors if present
                if "node_errors" in error_json:
                    logger.error(f"Node errors: {error_json['node_errors']}")
            except Exception as e:
                logger.error(f"Failed to parse error JSON: {e}")
            resp.raise_for_status()
        response_data = resp.json()
        
        prompt_id = response_data.get("prompt_id")
        if not prompt_id:
            error_msg = response_data.get("error", "No error details")
            node_errors = response_data.get("node_errors", {})
            raise ValueError(
                f"No prompt_id in response. Error: {error_msg}, "
                f"Node errors: {node_errors}"
            )
        
        logger.info(f"Workflow submitted successfully. Prompt ID: {prompt_id}")
        return prompt_id
    
    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        resp = await self.client.get(f"/history/{prompt_id}")
        resp.raise_for_status()
        return resp.json().get(prompt_id, {})
    
    async def get_file(self, filename: str) -> bytes:
        resp = await self.client.get(f"/view?filename={filename}")
        resp.raise_for_status()
        return resp.content
    
    async def close(self):
        await self.client.aclose()

