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

    async def update_progress(self, job_id: str, current_step: int, total_steps: int) -> bool:
        """Report sampler progress upstream so clients can show a step counter.

        Throttled by the bridge's WS loop — this call is not rate-limited itself,
        but the bridge only invokes it every ~2 seconds.

        Returns True on success, False on any failure. Failures are non-fatal:
        a dropped progress update must never break a job.
        """
        try:
            response = await self.client.post(
                "/v2/generate/progress",
                headers=self.headers,
                json={
                    "id": job_id,
                    "current_step": current_step,
                    "total_steps": total_steps,
                },
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.debug(
                f"Progress update for job {job_id} failed [{exc.response.status_code}]: "
                f"{exc.response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.debug(f"Progress update error for job {job_id}: {e}")
            return False

    async def send_preview(
        self,
        job_id: str,
        image_bytes: bytes,
        mime: str = "image/jpeg",
        step: int = 0,
    ) -> bool:
        """Stream a preview frame for an active generation to the API.

        Forwarded from ComfyUI's binary `b_preview` WebSocket frames so end users
        can see images forming during generation (~6 previews over a 30-step run).

        Raw bytes in the body — no base64, no JSON wrapper. Step number rides
        in `X-Step`. Failures are eaten: a dropped preview must never break a job.
        """
        if not image_bytes:
            return False
        try:
            response = await self.client.post(
                f"/v2/generate/preview/{job_id}",
                headers={**self.headers, "Content-Type": mime, "X-Step": str(step)},
                content=image_bytes,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.debug(
                f"Preview upload for job {job_id} failed [{exc.response.status_code}]: "
                f"{exc.response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.debug(f"Preview upload error for job {job_id}: {e}")
            return False

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
