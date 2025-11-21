import logging
import httpx
from typing import List, Any, Dict, Optional
from .config import Settings

logger = logging.getLogger(__name__)

# Disable httpx logging in API client too
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)


class APIClient:
    def __init__(self):
        Settings.validate()
        self.client = httpx.AsyncClient(
            base_url=Settings.GRID_API_URL, 
            timeout=60,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.headers = {
            "apikey": Settings.GRID_API_KEY,
            "Content-Type": "application/json",
        }
        # Cache for job metadata to reduce API calls
        self._job_cache: Dict[str, Dict[str, Any]] = {}

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

        logger.debug(f"Polling for jobs with {len(payload.get('models', []))} models")
        
        try:
            response = await self.client.post(
                "/v2/generate/pop", headers=self.headers, json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Cache job metadata for potential reuse
            if result.get("id"):
                job_id = result.get("id")
                self._job_cache[job_id] = result
                logger.info(f"Received job {job_id} for model {result.get('model', 'unknown')}")
            
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"pop_job payload: {payload}")
            logger.error(
                f"pop_job response [{e.response.status_code}]: {e.response.text}"
            )
            raise

    async def cancel_job(self, job_id: str) -> None:
        payload = {"id": job_id}
        
        try:
            response = await self.client.post(
                "/v2/generate/cancel", headers=self.headers, json=payload
            )
            response.raise_for_status()
            logger.info(f"Successfully cancelled job {job_id}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to cancel job {job_id}: {e.response.status_code} - {e.response.text}")

    async def submit_result(self, payload: Dict[str, Any]) -> None:
        job_id = payload.get("id")
        media_type = payload.get("media_type", "image")
        
        logger.info(f"Submitting {media_type} result for job {job_id}")
        
        try:
            response = await self.client.post(
                "/v2/generate/submit", headers=self.headers, json=payload
            )
            response.raise_for_status()
            
            # Clean up job cache
            if job_id in self._job_cache:
                del self._job_cache[job_id]
            
            logger.info(f"Successfully submitted {media_type} result for job {job_id}")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to submit result for job {job_id}: {e.response.status_code} - {e.response.text}")
            raise
