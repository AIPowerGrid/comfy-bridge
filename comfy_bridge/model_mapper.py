import httpx
import json
import os
from typing import Dict, List, Optional

from .config import Settings


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
        "wan2.2_t2v": "wan2_2_t2v_14b.json",
        "wan2.2": "wan2_2_t2v_14b.json",
        "wan2.2-t2v-a14b": "wan2_2_t2v_14b.json",
        "wan2.2-t2v-a14b-hq": "wan2_2_t2v_14b_hq.json",
        "wan2_2_t2v_14b_hq": "wan2_2_t2v_14b_hq.json",
        "wan2.2_ti2v_5B": "wan2_2_5B_ti2v.json",
        "wan2.2-ti2v-5b": "wan2_2_5B_ti2v.json",
        "wan2_2_5B_ti2v": "wan2_2_5B_ti2v.json",
    }

    def __init__(self):
        self.available_models: List[str] = []
        # Maps Grid model name -> workflow filename
        self.workflow_map: Dict[str, str] = {}
        # Maps model file name (e.g., some_model.safetensors) -> Grid model name (key in reference)
        self.reference_file_to_grid_name: Dict[str, str] = {}

    async def initialize(self, comfy_url: str):
        # Get models available in Comfy (optional; currently informational)
        self.available_models = await fetch_comfyui_models(comfy_url)

        # Load AI Power Grid local reference for model-file → Grid model name resolution
        self.reference_file_to_grid_name = self._load_local_reference()

        # If WORKFLOW_FILE is set, only use models derived from those workflows (no defaults)
        if Settings.WORKFLOW_FILE:
            self._build_workflow_map_from_env()
        else:
            # No env override: fall back to static defaults
            self._build_workflow_map()

        print(
            f"Initialized workflow mapper with {len(self.workflow_map)} Grid models mapped to workflows"
        )

    def _build_workflow_map(self):
        """Build mapping from Grid models to ComfyUI workflows"""
        self.workflow_map = self.DEFAULT_WORKFLOW_MAP.copy()

    def _load_local_reference(self) -> Dict[str, str]:
        """Load Grid model reference and return mapping path → Grid model name.

        Supports both local directories/files and HTTP(S) URLs.
        If the env var points to a directory, appends 'stable_diffusion.json'.
        If it points directly to a JSON file, uses it as-is.
        """
        reference_map: Dict[str, str] = {}
        try:
            root = Settings.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH or ""

            # Decide final location (file path or URL)
            is_url = root.startswith("http://") or root.startswith("https://")
            if is_url:
                if root.rstrip("/").lower().endswith(".json"):
                    location = root
                else:
                    location = root.rstrip("/") + "/stable_diffusion.json"
            else:
                if root.lower().endswith(".json"):
                    location = root
                else:
                    location = os.path.join(root or "grid-image-model-reference", "stable_diffusion.json")

            # Load JSON from the decided location
            if is_url:
                with httpx.Client() as client:
                    resp = client.get(location)
                    resp.raise_for_status()
                    data = resp.json()
            else:
                with open(location, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Build mapping: file path → grid model name
            loaded_models = 0
            for grid_model_name, info in data.items():
                if not isinstance(info, dict):
                    continue
                files_list = info.get("files")
                if files_list is None:
                    files_list = (info.get("config", {}) or {}).get("files", [])
                for file_info in files_list or []:
                    path_value = (file_info or {}).get("path")
                    if path_value:
                        reference_map[path_value] = grid_model_name
                        loaded_models += 1

            print(
                f"Loaded model reference from {'URL' if is_url else 'file'}: {location} (entries: {loaded_models})"
            )
        except Exception as e:
            print(f"Warning: failed to load model reference: {e}")
        return reference_map

    def _iter_env_workflow_files(self) -> List[str]:
        """Resolve workflow filenames from env settings.

        - WORKFLOW_FILE can be a single filename or comma-separated list
        - Files are resolved relative to Settings.WORKFLOW_DIR
        """
        configured = Settings.WORKFLOW_FILE or ""
        workflow_filenames = [
            w.strip() for w in configured.split(",") if w and w.strip()
        ]
        resolved_paths: List[str] = []
        for filename in workflow_filenames:
            abs_path = os.path.join(Settings.WORKFLOW_DIR, filename)
            if os.path.exists(abs_path):
                resolved_paths.append(abs_path)
            else:
                print(f"Warning: workflow file not found from env: {abs_path}")
        return resolved_paths

    def _extract_model_files_from_workflow(self, workflow_path: str) -> List[str]:
        """Extract model file names from a workflow JSON file.

        Supports both simple format (direct node objects) and ComfyUI format (nodes array).
        - CheckpointLoaderSimple.ckpt_name (SD/SDXL ckpt)
        - UNETLoader.unet_name (e.g., Flux-style UNET weights)
        - CLIPLoader.clip_name (e.g., WAN2 clip models)
        - VAELoader.vae_name (e.g., WAN2 VAE)
        """
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                wf = json.load(f)
        except Exception as e:
            print(f"Warning: failed to read workflow '{workflow_path}': {e}")
            return []

        # Extract workflow filename for better logging
        filename = os.path.basename(workflow_path)

        model_files: List[str] = []
        # Handle ComfyUI format (nodes array)
        if isinstance(wf, dict) and "nodes" in wf:
            nodes = wf.get("nodes", [])
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                class_type = node.get("type")  # ComfyUI uses "type" instead of "class_type"
                if class_type == "CheckpointLoaderSimple":
                    inputs = node.get("inputs", {}) or {}
                    ckpt_name = inputs.get("ckpt_name")
                    if isinstance(ckpt_name, str) and ckpt_name:
                        model_files.append(ckpt_name)
                elif class_type == "UNETLoader":
                    # Try inputs first
                    inputs = node.get("inputs", {}) or {}
                    unet_name = inputs.get("unet_name")
                    if isinstance(unet_name, str) and unet_name:
                        model_files.append(unet_name)
                    else:
                        # Try properties.models for ComfyUI format
                        properties = node.get("properties", {}) or {}
                        models = properties.get("models", [])
                        if models and isinstance(models[0], dict):
                            model_name = models[0].get("name")
                            if isinstance(model_name, str) and model_name:
                                model_files.append(model_name)
                elif class_type in ["CLIPLoader", "VAELoader"]:
                    inputs = node.get("inputs", {}) or {}
                    model_name = inputs.get("clip_name") or inputs.get("vae_name")
                    if isinstance(model_name, str) and model_name:
                        model_files.append(model_name)
        # Handle simple format (direct node objects)
        elif isinstance(wf, dict):
            for _, node in wf.items():
                if not isinstance(node, dict):
                    continue
                class_type = node.get("class_type")
                if class_type == "CheckpointLoaderSimple":
                    inputs = node.get("inputs", {}) or {}
                    ckpt_name = inputs.get("ckpt_name")
                    if isinstance(ckpt_name, str) and ckpt_name:
                        model_files.append(ckpt_name)
                elif class_type == "UNETLoader":
                    inputs = node.get("inputs", {}) or {}
                    unet_name = inputs.get("unet_name")
                    if isinstance(unet_name, str) and unet_name:
                        model_files.append(unet_name)
                elif class_type == "CLIPLoader":
                    inputs = node.get("inputs", {}) or {}
                    clip_name = inputs.get("clip_name")
                    if isinstance(clip_name, str) and clip_name:
                        model_files.append(clip_name)
                elif class_type == "VAELoader":
                    inputs = node.get("inputs", {}) or {}
                    vae_name = inputs.get("vae_name")
                    if isinstance(vae_name, str) and vae_name:
                        model_files.append(vae_name)
        return model_files

    def _resolve_file_to_grid_model(self, file_name: str) -> Optional[str]:
        """Resolve a local workflow file name to a Grid model name (exact match only)."""
        return self.reference_file_to_grid_name.get(file_name)

    def _build_workflow_map_from_env(self):
        """Build workflow map based on env-specified workflows.

        For each workflow file listed in env, find checkpoint files and resolve them to
        Grid model names via the local reference; then map Grid model → workflow filename.
        """
        self.workflow_map = {}
        env_workflows = self._iter_env_workflow_files()
        for abs_path in env_workflows:
            filename = os.path.basename(abs_path)
            model_files = self._extract_model_files_from_workflow(abs_path)
            for model_file in model_files:
                grid_model_name: Optional[str] = self._resolve_file_to_grid_model(
                    model_file
                )
                if grid_model_name:
                    self.workflow_map[grid_model_name] = filename
                else:
                    print(
                        f"Info: model file '{model_file}' from '{filename}' not found in reference; not advertising"
                    )

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
