import httpx
from typing import Dict, List


async def fetch_comfyui_models(comfy_url: str) -> List[str]:
    endpoints = ["/object_info", "/model_list"]

    async with httpx.AsyncClient(base_url=comfy_url, timeout=10) as client:
        for endpoint in endpoints:
            try:
                response = await client.get(endpoint)
                response.raise_for_status()
                data = response.json()

                models = []
                if endpoint == "/object_info":
                    # Get checkpoint models
                    checkpoint_models = (
                        data.get("CheckpointLoaderSimple", {})
                        .get("input", {})
                        .get("required", {})
                        .get("ckpt_name", [[]])[0]
                    )
                    models.extend(checkpoint_models)
                    
                    # Get Flux models
                    flux_models = (
                        data.get("FluxLoader", {})
                        .get("input", {})
                        .get("required", {})
                        .get("model_name", [[]])[0]
                    )
                    models.extend(flux_models)
                elif endpoint == "/model_list":
                    models = data.get("checkpoints", []) + data.get("models", [])

                if models:
                    return models

            except Exception as e:
                print(f"Warning: {endpoint} fetch failed: {e}")

    return []


class ModelMapper:
    # Map Grid model names to ComfyUI workflow files
    DEFAULT_WORKFLOW_MAP = {
        "stable_diffusion_1.5": "Dreamshaper.json",
        "stable_diffusion_2.1": "Dreamshaper.json", 
        "sdxl": "turbovision.json",
        "sdxl turbo": "turbovision.json",
        "SDXL 1.0": "turbovision.json",
        "sdxl-turbo": "turbovision.json",
        "sd_xl_turbo": "turbovision.json",
        "juggernaut_xl": "turbovision.json",
        "playground_v2": "turbovision.json",
        "dreamshaper_8": "Dreamshaper.json",
        "stable_diffusion": "Dreamshaper.json",
        "Flux.1-Krea-dev Uncensored (fp8+CLIP+VAE)": "flux1_krea_dev.json",
    }

    def __init__(self):
        self.available_models: List[str] = []
        self.workflow_map: Dict[str, str] = {}

    async def initialize(self, comfy_url: str):
        self.available_models = await fetch_comfyui_models(comfy_url)

        if not self.available_models:
            print("Warning: No models detected in ComfyUI")
            return

        self._build_workflow_map()

        print(
            f"Initialized workflow mapper with {len(self.workflow_map)} Grid models mapped to workflows"
        )

    def _build_workflow_map(self):
        """Build mapping from Grid models to ComfyUI workflows"""
        self.workflow_map = self.DEFAULT_WORKFLOW_MAP.copy()

    def get_workflow_file(self, horde_model_name: str) -> str:
        """Get the workflow file for a Grid model"""
        return (
            self.workflow_map.get(horde_model_name)
            or next(
                (
                    v
                    for k, v in self.workflow_map.items()
                    if horde_model_name.lower() in k.lower()
                ),
                None,
            )
            or "Dreamshaper.json"  # Default workflow
        )

    def get_available_horde_models(self) -> List[str]:
        return list(self.workflow_map.keys())


model_mapper = ModelMapper()


async def initialize_model_mapper(comfy_url: str):
    await model_mapper.initialize(comfy_url)


def get_horde_models() -> List[str]:
    return model_mapper.get_available_horde_models()


def get_workflow_file(horde_model_name: str) -> str:
    return model_mapper.get_workflow_file(horde_model_name)
