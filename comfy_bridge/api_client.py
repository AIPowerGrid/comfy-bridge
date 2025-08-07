import logging
import httpx
from typing import List, Any, Dict
from .config import Settings

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        Settings.validate()
        self.client = httpx.AsyncClient(base_url=Settings.GRID_API_URL, timeout=60)
        self.headers = {
            "apikey": Settings.GRID_API_KEY,
            "Content-Type": "application/json"
        }

    async def pop_job(self, models: List[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": Settings.GRID_WORKER_NAME,
            "worker_type": "image",
            "max_pixels": Settings.MAX_PIXELS,
            "nsfw": Settings.NSFW,
            "threads": Settings.THREADS,
            "require_upfront_kudos": False,
            "img2img": True,
            "painting": True,
            "post_processing": True,
            "bridge_agent": "comfy-bridge/0.1",
            "models": models
        }
        if models:
            payload["models"] = models

        logger.debug(f"pop_job sending payload: {payload}")
        if models:
            payload["models"] = models

        try:
            response = await self.client.post(
                "/v2/generate/pop", headers=self.headers, json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"pop_job payload: {payload}")
            logger.error(f"pop_job response [{e.response.status_code}]: {e.response.text}")
            raise

    async def submit_result(self, payload: Dict[str, Any]) -> None:
        """Submit a completed job result back to the AI Power Grid."""
        response = await self.client.post(
            "/v2/generate/submit", headers=self.headers, json=payload
        )
        response.raise_for_status()