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
        """Load local Grid model reference and return mapping path → Grid model name.

        Expects repository cloned at project_root/grid-image-model-reference/stable_diffusion.json
        """
        reference_map: Dict[str, str] = {}
        try:
            project_root = os.getcwd()
            reference_path = os.path.join(
                project_root, "grid-image-model-reference", "stable_diffusion.json"
            )
            with open(reference_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Structure: { "GridModelName": { ..., "files": [ {"path": "..."}, ... ] }, ... }
            for grid_model_name, info in data.items():
                if not isinstance(info, dict):
                    continue
                # Some entries store files directly under the model, others under config.files
                files_list = info.get("files")
                if files_list is None:
                    files_list = (info.get("config", {}) or {}).get("files", [])
                for file_info in files_list or []:
                    path_value = file_info.get("path")
                    if path_value:
                        reference_map[path_value] = grid_model_name
        except Exception as e:
            print(f"Warning: failed to load local model reference: {e}")
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

        - CheckpointLoaderSimple.ckpt_name (SD/SDXL ckpt)
        - UNETLoader.unet_name (e.g., Flux-style UNET weights)
        """
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                wf = json.load(f)
        except Exception as e:
            print(f"Warning: failed to read workflow '{workflow_path}': {e}")
            return []

        model_files: List[str] = []
        if isinstance(wf, dict):
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
