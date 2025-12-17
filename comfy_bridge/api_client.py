import asyncio
import logging
import json
import httpx  # type: ignore  # httpx installed via requirements.txt in Docker
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
        models_to_use = models or Settings.GRID_MODELS
        payload: Dict[str, Any] = {
            "name": Settings.GRID_WORKER_NAME,
            "max_pixels": Settings.MAX_PIXELS,  # Very high - accept any resolution
            "nsfw": Settings.NSFW,
            "threads": Settings.THREADS,  # Indicate higher capacity
            "require_upfront_kudos": False,
            "allow_img2img": True,
            "allow_painting": True,
            "allow_post_processing": True,
            "allow_controlnet": True,
            "allow_sdxl_controlnet": True,
            "allow_lora": True,
            "allow_unsafe_ipaddr": True,
            "extra_slow_worker": False,
            "limit_max_steps": False,
            "bridge_agent": "AI Horde Worker reGen:10.1.0:https://github.com/Haidra-Org/horde-worker-reGen",
            "models": models_to_use,
            "blacklist": [],
            "amount": 1,
            "skip_models": False,  # Don't skip any model requests
        }

        # Debug: Log models being advertised (every 50th call to reduce noise)
        if not hasattr(self, '_pop_count'):
            self._pop_count = 0
        self._pop_count += 1
        
        if self._pop_count == 1 or self._pop_count % 50 == 0:
            logger.info(f"📋 pop_job request #{self._pop_count}:")
            logger.info(f"   API URL: {Settings.GRID_API_URL}/v2/generate/pop")
            logger.info(f"   Worker: {Settings.GRID_WORKER_NAME}")
            logger.info(f"   Models ({len(models_to_use)}): {models_to_use}")
            logger.info(f"   max_pixels: {Settings.MAX_PIXELS}, nsfw: {Settings.NSFW}, threads: {Settings.THREADS}")

        try:
            response = await self.client.post(
                "/v2/generate/pop", headers=self.headers, json=payload
            )
            response.raise_for_status()
            result = response.json()

            # Get skipped jobs info early for use in logging
            skipped = result.get("skipped", {})

            # Cache job metadata for potential reuse
            if result.get("id"):
                job_id = result.get("id")
                self._job_cache[job_id] = result
                logger.info(f"✅ Received job {job_id} for model {result.get('model', 'unknown')}")
            else:
                # Log full response when no job (periodically or when models are skipped)
                if self._pop_count == 1 or self._pop_count % 50 == 0 or skipped.get("models", 0) > 0:
                    if Settings.DEBUG or skipped.get("models", 0) > 0:
                        logger.info(f"📭 No job received. Full API response: {json.dumps(result, indent=2)}")
            
            # Log skipped jobs for debugging
            interesting_skips = {k: v for k, v in skipped.items() if v > 0}
            if interesting_skips:
                # Log skipped jobs periodically (every 50th poll) or on first poll, OR always if models are skipped
                should_log = self._pop_count == 1 or self._pop_count % 50 == 0 or skipped.get("models", 0) > 0
                if should_log:
                    logger.info(f"ℹ️  Skipped jobs (poll #{self._pop_count}): {interesting_skips}")
                    # Explain what the skips mean
                    if skipped.get("max_pixels", 0) > 0:
                        logger.info(f"   → {skipped['max_pixels']} jobs skipped: requested resolution exceeds max_pixels ({Settings.MAX_PIXELS})")
                    if skipped.get("nsfw", 0) > 0:
                        logger.info(f"   → {skipped['nsfw']} jobs skipped: NSFW content (GRID_NSFW={Settings.NSFW})")
                    if skipped.get("models", 0) > 0:
                        logger.info(f"   → {skipped['models']} jobs skipped: model mismatch (jobs exist but for models we don't support)")
                        logger.info(f"      We are advertising: {models_to_use[:10]}{'...' if len(models_to_use) > 10 else ''}")
                        # Check which models actually have jobs in the queue
                        try:
                            models_status = await self.get_models_status()
                            if models_status:
                                if isinstance(models_status, list):
                                    models_with_jobs = []
                                    for model_info in models_status:
                                        if isinstance(model_info, dict):
                                            name = model_info.get("name", "")
                                            queued = model_info.get("queued", 0)
                                            if queued > 0:
                                                models_with_jobs.append((name, queued))
                                    
                                    if models_with_jobs:
                                        logger.info(f"      Models with queued jobs:")
                                        for name, queued in sorted(models_with_jobs, key=lambda x: -x[1])[:10]:
                                            supported = "✓" if name in models_to_use else "✗"
                                            logger.info(f"         {supported} {name}: {queued} jobs")
                                    else:
                                        logger.info(f"      No models with queued jobs found in status response")
                                else:
                                    logger.info(f"      Models status response is not a list: {type(models_status)}")
                                    logger.debug(f"      Response content: {models_status}")
                            else:
                                logger.info(f"      Could not get models status (empty response)")
                        except Exception as e:
                            logger.warning(f"      Could not check queue status: {e}", exc_info=Settings.DEBUG)
                        # Always log full response when models are skipped to help diagnose
                        logger.info(f"      Full API response: {json.dumps(result, indent=2)}")
                        # Log full response details if available
                        if "skipped_info" in result:
                            logger.info(f"      Skipped details: {result.get('skipped_info', {})}")
                    if skipped.get("worker_id", 0) > 0:
                        logger.info(f"   → {skipped['worker_id']} jobs skipped: worker ID issue")
                    if skipped.get("performance", 0) > 0:
                        logger.info(f"   → {skipped['performance']} jobs skipped: performance requirements")

            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"pop_job payload: {json.dumps(payload, indent=2)}")
            logger.error(
                f"pop_job response [{e.response.status_code}]: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"pop_job unexpected error: {type(e).__name__}: {e}")
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
            # 404 is expected if job was never submitted (e.g., rejected during validation)
            if e.response.status_code == 404:
                logger.debug(f"Job {job_id} not found for cancellation (may have been rejected before submission)")
            else:
                logger.error(f"Failed to cancel job {job_id}: {e.response.status_code} - {e.response.text}")

    async def submit_result(self, payload: Dict[str, Any]) -> None:
        job_id = payload.get("id")
        media_type = payload.get("media_type", "image")

        logger.info(f"Submitting {media_type} result for job {job_id}")

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Log what we're sending
                payload_debug = {k: v for k, v in payload.items() if k != "generation"}
                payload_debug["generation_length"] = len(payload.get("generation", ""))
                logger.info(f"DEBUG submit payload: {json.dumps(payload_debug)}")
                
                response = await self.client.post(
                    "/v2/generate/submit", headers=self.headers, json=payload
                )
                
                # Log the response
                logger.info(f"DEBUG submit response status: {response.status_code}")
                try:
                    resp_json = response.json()
                    logger.info(f"DEBUG submit response body: {json.dumps(resp_json)}")
                except:
                    logger.info(f"DEBUG submit response text: {response.text[:500]}")
                
                response.raise_for_status()

                # Clean up job cache
                if job_id in self._job_cache:
                    del self._job_cache[job_id]

                logger.info(f"Successfully submitted {media_type} result for job {job_id}")
                return

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Network error submitting result on attempt {attempt + 1}/{max_retries}: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to submit result after {max_retries} attempts: {e}")
                    raise
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                parsed_error = None
                try:
                    parsed_error = e.response.json()
                except (ValueError, json.JSONDecodeError):
                    parsed_error = None

                if (
                    e.response.status_code == 400
                    and isinstance(parsed_error, dict)
                    and parsed_error.get("rc") == "AbortedGen"
                ):
                    logger.error(
                        "Job %s was aborted upstream due to slow processing (AbortedGen). "
                        "Dropping the result and continuing. Message: %s",
                        job_id,
                        parsed_error.get("message", "Unknown reason"),
                    )
                    self._job_cache.pop(job_id, None)
                    return

                if isinstance(parsed_error, dict):
                    logger.error(
                        f"Failed to submit result for job {job_id}: {e.response.status_code}"
                    )
                    logger.error(f"Error response: {json.dumps(parsed_error, indent=2)}")
                else:
                    logger.error(
                        f"Failed to submit result for job {job_id}: {e.response.status_code} - {error_text}"
                    )

                # Log payload info for debugging (without the large base64)
                payload_debug = {k: v for k, v in payload.items() if k != "generation"}
                payload_debug["generation"] = f"<base64 data, length: {len(payload.get('generation', ''))}>"
                logger.debug(f"Payload sent: {json.dumps(payload_debug, indent=2)}")
                raise

    async def get_request_status(self, job_id: str) -> Dict[str, Any]:
        """
        Fetch the current status for a previously-submitted request.  Primarily
        used for debugging to verify that the Horde accepted our payload.
        """
        if not job_id:
            raise ValueError("job_id is required for request status checks.")

        try:
            response = await self.client.get(
                f"/v2/generate/status/{job_id}", headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.debug(
                "Status check for job %s failed [%s]: %s",
                job_id,
                exc.response.status_code if exc.response else "unknown",
                exc.response.text if exc.response else exc,
            )
            raise

    async def get_models_status(self) -> Dict[str, Any]:
        """
        Fetch current status of all models including queue counts.
        This shows what models have jobs waiting.
        """
        try:
            response = await self.client.get(
                "/v2/status/models", headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"Failed to get models status [{exc.response.status_code}]: {exc.response.text}"
            )
            return {}
        except Exception as e:
            logger.error(f"Error getting models status: {e}")
            return {}
