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
            timeout=240,  # 4 minutes (4x increase for video support)
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.headers = {
            "apikey": Settings.GRID_API_KEY,
            "Content-Type": "application/json",
        }
        # Cache for job metadata to reduce API calls
        self._job_cache: Dict[str, Dict[str, Any]] = {}

    async def pop_job(self, models: Optional[List[str]] = None) -> Dict[str, Any]:
        # Always use the provided models list - never fall back to Settings.GRID_MODELS
        # Settings.GRID_MODELS contains workflow filenames, not model names
        if models is None or len(models) == 0:
            logger.error("pop_job called with no models! This should not happen.")
            models = []
        models_to_use = models
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
            logger.info(f"   🔍 DETAILED MODEL INFO:")
            for i, model in enumerate(models_to_use, 1):
                logger.info(f"      {i}. '{model}' (repr: {repr(model)}, length: {len(model)}, lowercase: '{model.lower()}')")
            logger.info(f"   max_pixels: {Settings.MAX_PIXELS}, nsfw: {Settings.NSFW}, threads: {Settings.THREADS}")
            logger.info(f"   ⚠️  Model names are case-sensitive - API will match jobs exactly as shown above")
            
            # On first poll, also check worker status
            if self._pop_count == 1:
                try:
                    # Try to get worker info to see if it's recognized
                    logger.debug(f"   Checking if worker is recognized by API...")
                except Exception:
                    pass

        try:
            response = await self.client.post(
                "/v2/generate/pop", headers=self.headers, json=payload
            )
            
            # Check for 400 Bad Request with unrecognized models error
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if "unrecognised models" in error_data.get("message", "").lower() or "unrecognized models" in error_data.get("message", "").lower():
                        logger.error(f"❌ API rejected models: {models_to_use}")
                        logger.error(f"   Error: {error_data.get('message')}")
                        logger.error(f"   This usually means:")
                        logger.error(f"   1. Model names don't match blockchain registry")
                        logger.error(f"   2. Models need to be registered on-chain first")
                        logger.error(f"   3. Model names have wrong case or format")
                        logger.error(f"   Check blockchain registry for correct model names")
                        # Check if it's a case issue - suggest trying lowercase
                        for model in models_to_use:
                            model_lower = model.lower()
                            if model != model_lower:
                                logger.error(f"   💡 SUGGESTION: API may expect lowercase '{model_lower}' instead of '{model}'")
                                logger.error(f"      The model reference JSON has key '{model}' but 'name' field is '{model_lower}'")
                                logger.error(f"      Server may be validating against the 'name' field instead of the JSON key")
                except:
                    pass
            
            response.raise_for_status()
            result = response.json()

            # Get skipped jobs info early for use in logging
            skipped = result.get("skipped", {})
            if skipped.get("models", 0) > 0:
                logger.warning(f"   ⚠️  {skipped['models']} jobs skipped due to model mismatch")
                logger.warning(f"      This means jobs exist in queue but model names don't match exactly")
                logger.warning(f"      Advertised models: {models_to_use}")
                # Immediately fetch and analyze models status to diagnose the mismatch
                logger.warning(f"      🔍 DIAGNOSING MODEL MISMATCH...")
                try:
                    models_status = await self.get_models_status()
                    if models_status and isinstance(models_status, list):
                        logger.warning(f"      📊 Analyzing {len(models_status)} models from API...")
                        for model_info in models_status:
                            if isinstance(model_info, dict):
                                name = model_info.get("name", "")
                                jobs = model_info.get("jobs", 0)
                                queued = model_info.get("queued", 0)
                                if jobs > 0 or queued > 0:
                                        logger.warning(f"      • Queue has: '{name}' (repr: {repr(name)}, length: {len(name)}) - {jobs} jobs")
                                        # Check for case mismatch
                                        name_lower = name.lower()
                                        for adv_model in models_to_use:
                                            adv_lower = adv_model.lower()
                                            if name_lower == adv_lower:
                                                if name != adv_model:
                                                    logger.error(f"      ❌ CASE MISMATCH FOUND!")
                                                    logger.error(f"         • Queue model: '{name}' (repr: {repr(name)})")
                                                    logger.error(f"         • Advertised model: '{adv_model}' (repr: {repr(adv_model)})")
                                                    logger.error(f"         • Lowercase match: '{name_lower}' == '{adv_lower}'")
                                                    logger.error(f"         • 💡 SOLUTION: Change worker to advertise '{name}' (lowercase) to match queue")
                                                    logger.error(f"         •   OR recreate the job with model name '{adv_model}' (capital L) to match worker")
                                                else:
                                                    logger.error(f"      ❌ MODEL NAMES MATCH EXACTLY BUT JOB STILL SKIPPED!")
                                                    logger.error(f"         • This suggests the job in database has different model name than status API shows")
                                                    logger.error(f"         • Status API shows: '{name}' (might be normalized for display)")
                                                    logger.error(f"         • Database likely has: Different case or model name")
                                                    logger.error(f"         • 💡 SOLUTION: Change worker to advertise '{name}' (lowercase) to match queue")
                                                    logger.error(f"         •   OR recreate the job with model name '{adv_model}' to match worker")
                                                    logger.error(f"         • The models status API may normalize display, but database query uses stored value")
                                                    logger.error(f"         • Check the actual WPModels table for the job's stored model name")
                    else:
                        logger.warning(f"      ⚠️  Could not fetch models status: {models_status}")
                except Exception as e:
                    logger.error(f"      ❌ Failed to diagnose mismatch: {e}", exc_info=True)

            # Cache job metadata for potential reuse
            if result.get("id") or (result.get("ids") and len(result.get("ids", [])) > 0):
                job_id = result.get("id") or (result.get("ids", [])[0] if result.get("ids") else None)
                job_model = result.get("model")
                logger.info(f"✅ Job received (poll #{self._pop_count})")
                logger.info(f"   • Job ID: {job_id}")
                logger.info(f"   • Job model: '{job_model}' (repr: {repr(job_model) if job_model else 'None'})")
                logger.info(f"   • Advertised models: {models_to_use}")
                if job_model:
                    job_model_lower = job_model.lower()
                    matched = False
                    for adv_model in models_to_use:
                        if adv_model.lower() == job_model_lower:
                            if adv_model == job_model:
                                logger.info(f"   ✅ Model name matches exactly: '{job_model}' == '{adv_model}'")
                            else:
                                logger.warning(f"   ⚠️  Case mismatch but matched: '{job_model}' (job) vs '{adv_model}' (advertised)")
                            matched = True
                            break
                    if not matched:
                        logger.error(f"   ❌ Job model '{job_model}' doesn't match any advertised model!")
                self._job_cache[job_id] = result
                # API now uses wallet_address instead of wallet
                wallet_address = result.get("wallet_address", "") or result.get("wallet", "")
                wallet_info = f", wallet_address: {wallet_address[:10]}..." if wallet_address and len(wallet_address) > 10 else (f", wallet_address: {wallet_address}" if wallet_address else "")
                job_model = result.get('model', 'unknown')
                logger.info(f"✅ Received job {job_id}")
                logger.info(f"   📌 JOB MODEL: '{job_model}' (repr: {repr(job_model)}, length: {len(job_model)})")
                logger.info(f"   📌 We advertised: {models_to_use}")
                logger.info(f"   🔍 MODEL MATCHING CHECK:")
                if job_model in models_to_use:
                    logger.info(f"      ✅ Exact match found: '{job_model}' is in advertised models")
                else:
                    # Check case-insensitive match
                    job_model_lower = job_model.lower()
                    matched_lowercase = False
                    for adv_model in models_to_use:
                        if adv_model.lower() == job_model_lower:
                            matched_lowercase = True
                            logger.warning(f"      ⚠️  Case mismatch detected!")
                            logger.warning(f"         • Job model: '{job_model}' (repr: {repr(job_model)})")
                            logger.warning(f"         • Advertised: '{adv_model}' (repr: {repr(adv_model)})")
                            logger.warning(f"         • Lowercase match: '{job_model_lower}' == '{adv_model.lower()}'")
                            logger.warning(f"         • These differ only in case - API matched them anyway")
                            break
                    if not matched_lowercase:
                        logger.error(f"      ❌ No match found! Job model '{job_model}' doesn't match any advertised model")
                        logger.error(f"         • Job model: '{job_model}' (repr: {repr(job_model)})")
                        logger.error(f"         • Advertised models: {models_to_use}")
                        logger.error(f"         • This should not happen - investigate!")
            else:
                # Always log skipped reasons on first 10 polls, then periodically
                should_log_full = self._pop_count <= 10 or self._pop_count % 50 == 0
                should_log_skips = self._pop_count <= 10 or self._pop_count % 50 == 0 or any(v > 0 for v in skipped.values())
                
                if should_log_full:
                    logger.info(f"📭 No job received (poll #{self._pop_count})")
                    if Settings.DEBUG:
                        logger.info(f"   Full API response: {json.dumps(result, indent=2)}")
            
            # Log skipped jobs for debugging - always show on first polls
            interesting_skips = {k: v for k, v in skipped.items() if v > 0}
            should_log_skips = self._pop_count <= 10 or self._pop_count % 50 == 0 or bool(interesting_skips)
            
            if should_log_skips:
                if interesting_skips:
                    logger.info(f"ℹ️  Skipped jobs (poll #{self._pop_count}): {interesting_skips}")
                else:
                    logger.info(f"ℹ️  Skipped jobs (poll #{self._pop_count}): None (all skipped counts are 0)")
                    # Explain what the skips mean
                    if skipped.get("max_pixels", 0) > 0:
                        logger.info(f"   → {skipped['max_pixels']} jobs skipped: requested resolution exceeds max_pixels ({Settings.MAX_PIXELS})")
                    if skipped.get("nsfw", 0) > 0:
                        logger.info(f"   → {skipped['nsfw']} jobs skipped: NSFW content (GRID_NSFW={Settings.NSFW})")
                    if skipped.get("models", 0) > 0:
                        logger.warning(f"   → {skipped['models']} jobs skipped: model mismatch (jobs exist but for models we don't support)")
                        logger.warning(f"      📋 MODELS WE ARE ADVERTISING ({len(models_to_use)}): {models_to_use}")
                        logger.warning(f"      🔍 Each model name is case-sensitive - exact match required!")
                        logger.warning(f"      💡 If jobs exist for similar model names, check for case mismatches above")
                        # Check which models actually have jobs in the queue
                        logger.info(f"      Fetching models status from API...")
                        try:
                            models_status = await self.get_models_status()
                            logger.info(f"      Models status API returned: type={type(models_status).__name__}, len={len(models_status) if hasattr(models_status, '__len__') else 'N/A'}")
                            
                            if models_status:
                                if isinstance(models_status, list):
                                    models_with_jobs = []
                                    supported_with_jobs = []
                                    unsupported_with_jobs = []
                                    
                                    for model_info in models_status:
                                        if isinstance(model_info, dict):
                                            name = model_info.get("name", "")
                                            queued = model_info.get("queued", 0)  # This is "things" (megapixels), not job count!
                                            jobs = model_info.get("jobs", 0)  # Actual job count
                                            if queued > 0 or jobs > 0:
                                                models_with_jobs.append((name, queued, jobs))
                                                if name in models_to_use:
                                                    supported_with_jobs.append((name, queued, jobs))
                                                else:
                                                    unsupported_with_jobs.append((name, queued, jobs))
                                    
                                    logger.info(f"      Found {len(models_with_jobs)} models with queued work")
                                    
                                    # Show supported models with jobs first
                                    if supported_with_jobs:
                                        logger.info(f"      ✅ SUPPORTED MODELS WITH JOBS ({len(supported_with_jobs)}):")
                                        for name, queued, jobs in sorted(supported_with_jobs, key=lambda x: -x[1]):
                                            logger.info(f"         ✓ '{name}' - {jobs} jobs ({queued:.0f} megapixels)")
                                    else:
                                        logger.info(f"      ⚠️  NO SUPPORTED MODELS HAVE JOBS IN QUEUE")
                                    
                                    # Show unsupported models with jobs
                                    if unsupported_with_jobs:
                                        logger.info(f"      ❌ UNSUPPORTED MODELS WITH JOBS ({len(unsupported_with_jobs)}):")
                                        for name, queued, jobs in sorted(unsupported_with_jobs, key=lambda x: -x[1])[:20]:
                                            logger.info(f"         ✗ '{name}' - {jobs} jobs ({queued:.0f} megapixels)")
                                        
                                        # Check for near-matches (case-insensitive, partial matches)
                                        logger.info(f"      🔍 CHECKING FOR NAME MISMATCHES...")
                                        logger.info(f"      📋 DETAILED COMPARISON:")
                                        logger.info(f"         • Models we advertise: {models_to_use}")
                                        logger.info(f"         • Models with jobs in queue: {[n for n, _, _ in unsupported_with_jobs]}")
                                        
                                        case_mismatches_found = False
                                        for unsupported_name, _, _ in unsupported_with_jobs[:10]:  # Check first 10
                                            unsupported_lower = unsupported_name.lower()
                                            logger.info(f"         🔎 Checking '{unsupported_name}' (queue) against advertised models...")
                                            for supported_name in models_to_use:
                                                supported_lower = supported_name.lower()
                                                # Check for exact match (case-insensitive)
                                                if unsupported_lower == supported_lower:
                                                    case_mismatches_found = True
                                                    logger.warning(f"      ⚠️  CASE MISMATCH DETECTED!")
                                                    logger.warning(f"         • Queue model name: '{unsupported_name}' (length: {len(unsupported_name)}, repr: {repr(unsupported_name)})")
                                                    logger.warning(f"         • Advertised model name: '{supported_name}' (length: {len(supported_name)}, repr: {repr(supported_name)})")
                                                    logger.warning(f"         • Lowercase match: '{unsupported_lower}' == '{supported_lower}'")
                                                    logger.warning(f"         • ❌ These don't match due to case sensitivity!")
                                                    logger.warning(f"         • 💡 SOLUTION: Change worker to advertise '{unsupported_name}' to match queue")
                                                    logger.warning(f"         •   OR recreate the job with model name '{supported_name}' to match worker")
                                                # Check for partial match
                                                elif unsupported_lower in supported_lower or supported_lower in unsupported_lower:
                                                    logger.warning(f"      ⚠️  PARTIAL MATCH: '{unsupported_name}' (queue) might match '{supported_name}' (advertised)")
                                        
                                        if not case_mismatches_found:
                                            logger.info(f"         ✅ No case mismatches detected (all differences are spelling/name differences)")
                                        
                                        logger.info(f"      💡 TIP: If '{unsupported_with_jobs[0][0]}' should be supported, check:")
                                        logger.info(f"         - Model name spelling/casing in workflow mappings")
                                        logger.info(f"         - Model registration in ModelVault")
                                        logger.info(f"         - Workflow file exists for this model")
                                        logger.info(f"         - Jobs in queue were created with correct model name case")
                                    else:
                                        logger.info(f"      ✅ All models with jobs are supported")
                                    
                                    # Summary
                                    logger.info(f"      📊 SUMMARY:")
                                    logger.info(f"         • We advertise: {len(models_to_use)} model(s)")
                                    logger.info(f"         • Models with jobs: {len(models_with_jobs)}")
                                    logger.info(f"         • Supported models with jobs: {len(supported_with_jobs)}")
                                    logger.info(f"         • Unsupported models with jobs: {len(unsupported_with_jobs)}")
                                    if unsupported_with_jobs:
                                        logger.warning(f"         ⚠️  {skipped['models']} job(s) skipped because model names don't match!")
                                        logger.warning(f"         Check if these model names need to be added to your workflow mappings:")
                                        for name, _, jobs in unsupported_with_jobs[:5]:
                                            logger.warning(f"            - '{name}' ({jobs} jobs)")
                                    
                                    # Show all models with jobs for reference
                                    if models_with_jobs:
                                        logger.info(f"      📊 ALL MODELS WITH QUEUED WORK (sorted by queue size):")
                                        logger.info(f"         Note: 'queued' = megapixels of work, 'jobs' = actual job count")
                                        for name, queued, jobs in sorted(models_with_jobs, key=lambda x: -x[1])[:20]:
                                            supported = "✓" if name in models_to_use else "✗"
                                            logger.info(f"         {supported} '{name}' - {jobs} jobs ({queued:.0f} megapixels)")
                                else:
                                    logger.info(f"      Models status response is not a list: {type(models_status)}")
                                    logger.info(f"      Raw response: {str(models_status)[:500]}")
                            else:
                                logger.info(f"      Models status returned empty/None")
                        except Exception as e:
                            logger.error(f"      ❌ Failed to check queue status: {e}", exc_info=True)
                    if skipped.get("worker_id", 0) > 0:
                        logger.info(f"   → {skipped['worker_id']} jobs skipped: worker ID issue")
                    if skipped.get("performance", 0) > 0:
                        logger.info(f"   → {skipped['performance']} jobs skipped: performance requirements (worker too slow, jobs need fast workers)")
                    if skipped.get("performance_our_models", 0) > 0:
                        logger.warning(f"   ⚠️  {skipped['performance_our_models']} jobs FOR OUR MODELS skipped due to speed (worker.speed <= 0.5 MPS/s)")
                        logger.warning(f"      → Worker may be too slow - check performance metrics")
                    if skipped.get("max_pixels_our_models", 0) > 0:
                        logger.warning(f"   ⚠️  {skipped['max_pixels_our_models']} jobs FOR OUR MODELS skipped due to resolution")
                        logger.warning(f"      → Jobs exceed max_pixels ({Settings.MAX_PIXELS})")
                    if skipped.get("untrusted", 0) > 0:
                        logger.warning(f"   ⚠️  {skipped['untrusted']} jobs skipped: require trusted workers")
                        logger.warning(f"      → Worker needs to be trusted to accept these jobs")
                    if skipped.get("bridge_version", 0) > 0:
                        logger.warning(f"   ⚠️  {skipped['bridge_version']} jobs skipped: bridge capability mismatch")
                        logger.warning(f"      → Bridge version may be incompatible")
                    
                    # Debug info for matching jobs that exist but weren't assigned
                    if skipped.get("_debug_matching_model_jobs", 0) > 0:
                        matching = skipped['_debug_matching_model_jobs']
                        logger.info(f"   ℹ️  DEBUG: {matching} jobs exist for our models but weren't assigned")
                        logger.info(f"      This means jobs are being filtered by other conditions (NSFW, lora, resolution, etc.)")
            
            # If no skipped reasons but still no job, investigate further
            if not result.get("id") and not interesting_skips and (self._pop_count <= 10 or self._pop_count % 50 == 0):
                logger.warning(f"   ⚠️  No skipped reasons but no job assigned (poll #{self._pop_count})")
                logger.warning(f"      This is unusual - investigating possible causes...")
                
                # Check if there are actually jobs available
                try:
                    models_status = await self.get_models_status()
                    if models_status:
                        for model_info in models_status:
                            if isinstance(model_info, dict):
                                name = model_info.get("name", "")
                                jobs = model_info.get("jobs", 0)
                                if name in models_to_use and jobs > 0:
                                    logger.warning(f"      → Found {jobs} jobs for '{name}' but none assigned")
                                    logger.warning(f"      → Possible causes:")
                                    logger.warning(f"         1. Jobs may have specific requirements not in skipped counts")
                                    logger.warning(f"         2. API may be rate-limiting or throttling")
                                    logger.warning(f"         3. Jobs may be in a different state (processing, etc.)")
                                    logger.warning(f"         4. Worker may need to be trusted for these jobs")
                                    
                                    # Try to check worker status on first occurrence
                                    if self._pop_count == 1:
                                        workers_status = await self.get_workers_status()
                                        if workers_status:
                                            logger.info(f"      → Workers status available - checking if our worker is recognized...")
                                            # Log worker info if available
                                            if isinstance(workers_status, dict):
                                                our_worker = workers_status.get(Settings.GRID_WORKER_NAME)
                                                if our_worker:
                                                    logger.info(f"      → Our worker is recognized by API")
                                                else:
                                                    logger.warning(f"      → Our worker '{Settings.GRID_WORKER_NAME}' not found in workers list")
                                    
                                    logger.warning(f"      → RECOMMENDATION: Check API dashboard or contact API team")
                                    logger.warning(f"      → This appears to be a server-side issue, not a worker configuration problem")
                                    break
                except Exception as e:
                    logger.debug(f"      Could not check models status: {e}")

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

    async def submit_fault(self, job_id: str, error_message: str, seed: Optional[str] = None) -> None:
        """Report a job as faulted/failed to the Grid API.
        
        This tells the server that the job failed so it can be reassigned or marked as failed,
        rather than staying in 'processing' state indefinitely.
        """
        payload = {
            "id": job_id,
            "state": "faulted",
            "generation": "",  # Empty generation for faulted jobs
            "seed": seed or "0",
            "gen_metadata": [
                {
                    "type": "error",
                    "value": error_message[:500]  # Truncate to avoid API issues
                }
            ]
        }
        
        logger.info(f"Reporting job {job_id} as faulted: {error_message[:100]}...")
        
        try:
            response = await self.client.post(
                "/v2/generate/submit", headers=self.headers, json=payload
            )
            response.raise_for_status()
            logger.info(f"Successfully reported job {job_id} as faulted")
            
            # Clean up job cache
            if job_id in self._job_cache:
                del self._job_cache[job_id]
                
        except httpx.HTTPStatusError as e:
            # 400 with AbortedGen means job was already timed out/cancelled - that's fine
            error_text = e.response.text
            if e.response.status_code == 400 and "AbortedGen" in error_text:
                logger.info(f"Job {job_id} was already aborted by server (likely timeout)")
            elif e.response.status_code == 404:
                logger.debug(f"Job {job_id} not found for fault report (may have been cancelled)")
            else:
                logger.error(f"Failed to report fault for job {job_id}: {e.response.status_code} - {error_text}")
        except Exception as e:
            logger.error(f"Error reporting fault for job {job_id}: {e}")

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
                    # For video jobs, this is expected - videos take much longer than images
                    # The server's timeout is based on image generation speed (1 it/s)
                    # which is not applicable to video generation
                    is_video = media_type == "video"
                    r2_uploads = payload.get("r2_uploads", [])
                    
                    if is_video:
                        logger.warning(
                            "Job %s was marked as AbortedGen by server (video took longer than image timeout). "
                            "This is expected for video generation. Video was still generated and uploaded to R2.",
                            job_id,
                        )
                        if r2_uploads:
                            logger.info(
                                "Video is available at R2. The server's timeout is based on image generation speed "
                                "and does not account for video generation which naturally takes longer."
                            )
                    else:
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

    async def get_models_status(self) -> list:
        """
        Fetch current status of all models including queue counts.
        This shows what models have jobs waiting.
        Returns a list of model status dicts.
        """
        try:
            logger.debug(f"Fetching /v2/status/models...")
            response = await self.client.get(
                "/v2/status/models", headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Models status response: status={response.status_code}, type={type(data).__name__}, len={len(data) if hasattr(data, '__len__') else 'N/A'}, data={data}")
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"Failed to get models status [{exc.response.status_code}]: {exc.response.text[:500]}"
            )
            return []
        except Exception as e:
            logger.error(f"Error getting models status: {e}", exc_info=True)
            return []
    
    async def get_workers_status(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current status of workers to see if our worker is recognized.
        This helps diagnose why jobs aren't being assigned.
        """
        try:
            logger.debug(f"Fetching /v2/status/workers...")
            response = await self.client.get(
                "/v2/status/workers", headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # 404 is expected if endpoint doesn't exist
            if exc.response.status_code == 404:
                logger.debug("Workers status endpoint not available")
            else:
                logger.debug(f"Failed to get workers status [{exc.response.status_code}]: {exc.response.text[:200]}")
            return None
        except Exception as e:
            logger.debug(f"Error getting workers status: {e}")
            return None

    async def update_progress(self, job_id: str, current_step: int, total_steps: int) -> bool:
        """
        Report progress on an active generation job to the API.
        This allows clients (like Discord) to see real-time step progress.
        
        Args:
            job_id: The processing generation ID (from the popped job)
            current_step: Current step in the generation (e.g., 15)
            total_steps: Total steps for the generation (e.g., 30)
            
        Returns:
            True if update succeeded, False otherwise
        """
        payload = {
            "id": job_id,
            "current_step": current_step,
            "total_steps": total_steps,
        }
        
        try:
            response = await self.client.post(
                "/v2/generate/progress",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            # Don't log as error - job may have completed/faulted already
            logger.debug(
                f"Progress update for job {job_id} failed [{exc.response.status_code}]: {exc.response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.debug(f"Progress update error for job {job_id}: {e}")
            return False
