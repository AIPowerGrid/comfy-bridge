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

                if endpoint == "/object_info":
                    models = (
                        data.get("CheckpointLoaderSimple", {})
                        .get("input", {})
                        .get("required", {})
                        .get("ckpt_name", [[]])[0]
                    )
                elif endpoint == "/model_list":
                    models = data.get("checkpoints", []) + data.get("models", [])

                if models:
                    return models

            except Exception as e:
                print(f"Warning: {endpoint} fetch failed: {e}")

    return []


class ModelMapper:
    DEFAULT_MODEL_MAP = {
        "stable_diffusion_1.5": "v1-5-pruned-emaonly.safetensors",
        "stable_diffusion_2.1": "v2-1_768-ema-pruned.safetensors",
        "sdxl": "sdxl_base_1.0.safetensors",
        "sdxl turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "SDXL 1.0": "sd_xl_base_1.0.safetensors",
        "sdxl-turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "sd_xl_turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "juggernaut_xl": "juggernaut_xl.safetensors",
        "playground_v2": "playground_v2.safetensors",
        "dreamshaper_8": "dreamshaper_8.safetensors",
        "stable_diffusion": "v1-5-pruned-emaonly.safetensors",
        "Flux.1-Krea-dev Uncensored (fp8+CLIP+VAE)": "flux1KreaDev_fp8ClipWithVAE.safetensors",
    }

    def __init__(self):
        self.available_models: List[str] = []
        self.model_map: Dict[str, str] = {}
        self.default_model: str = ""

    async def initialize(self, comfy_url: str):
        self.available_models = await fetch_comfyui_models(comfy_url)

        if not self.available_models:
            print("Warning: No models detected in ComfyUI")
            return

        self.default_model = self.available_models[0]
        self._build_model_map()

        print(
            f"Initialized with {len(self.available_models)} models. Default: {self.default_model}"
        )

    def _build_model_map(self):
        lower_model_filenames = {name.lower(): name for name in self.available_models}

        for key, default_filename in self.DEFAULT_MODEL_MAP.items():
            for filename in lower_model_filenames:
                if key.replace("_", "").replace("-", "") in filename.replace(
                    "_", ""
                ).replace("-", ""):
                    self.model_map[key] = lower_model_filenames[filename]
                    break

    def get_model_filename(self, horde_model_name: str) -> str:
        return (
            self.model_map.get(horde_model_name)
            or next(
                (
                    v
                    for k, v in self.model_map.items()
                    if horde_model_name.lower() in k.lower()
                ),
                None,
            )
            or self.default_model
        )

    def get_available_horde_models(self) -> List[str]:
        return list(self.model_map.keys())


model_mapper = ModelMapper()


async def initialize_model_mapper(comfy_url: str):
    await model_mapper.initialize(comfy_url)


def get_horde_models() -> List[str]:
    return model_mapper.get_available_horde_models()


def map_model_name(horde_model_name: str) -> str:
    return model_mapper.get_model_filename(horde_model_name)
