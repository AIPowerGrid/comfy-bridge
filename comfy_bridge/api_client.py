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
            "amount": 1,
        }

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
        
        # Log detailed information about the payload for debugging
        logger.info(f"Submitting {media_type} result to API")
        if media_type == "video":
            # Add video-specific header for proper content handling
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json"
            headers["X-Media-Type"] = "video"
            
            # Additional logging for video submissions
            logger.info(f"Using video headers: {headers}")
            logger.info(f"Video base64 length: {len(payload.get('generation', ''))}")
            
            response = await self.client.post(
                "/v2/generate/submit", headers=headers, json=payload
            )
        else:
            # Standard image submission
            response = await self.client.post(
                "/v2/generate/submit", headers=self.headers, json=payload
            )
            
        # Handle response
        if response.status_code != 200:
            logger.error(f"API response status: {response.status_code}")
            logger.error(f"API response: {response.text}")
        response.raise_for_status()
