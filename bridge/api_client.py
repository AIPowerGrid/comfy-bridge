import logging
import httpx
from typing import List, Any, Dict, Optional
from .config import Settings

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self):
        Settings.validate()
        self.client = httpx.AsyncClient(base_url=Settings.GRID_API_URL, timeout=60)
        self.headers = {
            "apikey": Settings.GRID_API_KEY,
            "Content-Type": "application/json",
        }

    async def pop_job(self, models: Optional[List[str]] = None) -> Dict[str, Any]:
        # Get batch size from settings, default to 4 for efficient batching
        batch_amount = getattr(Settings, 'BATCH_SIZE', 4)
        
        payload: Dict[str, Any] = {
            "name": Settings.GRID_WORKER_NAME,
            "max_pixels": Settings.MAX_PIXELS,
            "nsfw": Settings.NSFW,
            "threads": Settings.THREADS,
            "require_upfront_kudos": False,
            "allow_img2img": True,
            "allow_painting": False,
            "allow_post_processing": True,
            "allow_controlnet": False,
            "allow_sdxl_controlnet": False,
            "allow_lora": True,
            "allow_unsafe_ipaddr": False,
            "extra_slow_worker": False,
            "limit_max_steps": False,
            "bridge_agent": "AI Horde Worker reGen:10.0.7:https://github.com/Haidra-Org/horde-worker-reGen",
            "models": models or Settings.GRID_MODELS,
            "blacklist": [],
            "amount": batch_amount,  # Request batch of images
        }
        
        logger.info(f"Requesting batch of {batch_amount} jobs")

        if models:
            payload["models"] = models

        logger.debug(f"pop_job sending payload: {payload}")
        try:
            response = await self.client.post(
                "/v2/generate/pop", headers=self.headers, json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"pop_job payload: {payload}")
            logger.error(
                f"pop_job response [{e.response.status_code}]: {e.response.text}"
            )
            raise

    async def submit_result(self, payload: Dict[str, Any]) -> None:
        """Submit a completed job result back to the AI Power Grid."""
        media_type = payload.get("media_type", "image")
        
        # For video submissions, we need a consistent approach that was working before
        # Don't modify headers or add any special handling that might break completion reporting
        
        # Log detailed information about the payload for debugging
        logger.info(f"Submitting {media_type} result to API")
        response = await self.client.post(
                "/v2/generate/submit", headers=self.headers, json=payload
        )
            
        # Handle response
        logger.info(f"API response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("API submission successful")
            try:
                resp_data = response.json()
                logger.info(f"API response: {resp_data}")
            except:
                logger.info(f"API response text: {response.text}")
        else:
            logger.error(f"API error response status: {response.status_code}")
            logger.error(f"API error response: {response.text}")
            
        response.raise_for_status()
