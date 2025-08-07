import asyncio
import logging
import httpx
from typing import List

from .api_client import APIClient
from .workflow import build_workflow
from .utils import encode_image
from .config import Settings
from .model_mapper import initialize_model_mapper, get_horde_models, map_model_name

logger = logging.getLogger(__name__)


class ComfyUIBridge:
    def __init__(self):
        self.api = APIClient()
        self.comfy = httpx.AsyncClient(base_url=Settings.COMFYUI_URL, timeout=300)
        self.supported_models: List[str] = []

    async def process_once(self):
        job = await self.api.pop_job(self.supported_models)
        job_id = job.get("id")
        if not job_id:
            return
        logger.info(f"Picked up job {job_id} with metadata: {job}")(
            self.supported_models
        )
        job_id = job.get("id")
        if not job_id:
            return

        wf = build_workflow(job)
        resp = await self.comfy.post("/prompt", json={"prompt": wf})
        resp.raise_for_status()
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            logger.error(f"No prompt_id for job {job_id}")
            return

        while True:
            hist = await self.comfy.get(f"/history/{prompt_id}")
            hist.raise_for_status()
            data = hist.json().get(prompt_id, {})
            outputs = data.get("outputs", {})
            if outputs:
                node_id, node_data = next(iter(outputs.items()))
                imgs = node_data.get("images", [])
                if imgs:
                    filename = imgs[0]["filename"]
                    img_resp = await self.comfy.get(f"/view?filename={filename}")
                    img_resp.raise_for_status()
                    image_bytes = img_resp.content
                    break
            await asyncio.sleep(1)

        b64 = encode_image(image_bytes)
        payload = {
            "id": job_id,
            "generation": b64,
            "state": "ok",
            "seed": int(job.get("payload", {}).get("seed", 0)),
        }
        await self.api.submit_result(payload)
        logger.info(
            f"Job {job_id} completed successfully with seed={payload.get('seed')}"
        )

    async def run(self):
        logger.info("Bridge starting...")
        await initialize_model_mapper(Settings.COMFYUI_URL)

        if Settings.GRID_MODELS:
            self.supported_models = Settings.GRID_MODELS
        else:
            self.supported_models = get_horde_models()
        logger.info(f"Advertising models: {self.supported_models}")

        while True:
            logger.info("Waiting for jobs...")
            try:
                await self.process_once()
            except Exception as e:
                logger.error(f"Error processing job: {e}")
            await asyncio.sleep(2)

    async def cleanup(self):
        await self.comfy.aclose()
        await self.api.client.aclose()
