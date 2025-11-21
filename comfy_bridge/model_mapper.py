import httpx
import json
import os
import logging
from typing import Dict, List, Optional

from .config import Settings

logger = logging.getLogger(__name__)


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
                # Only log warnings in debug mode to reduce noise
                pass

    return []


class ModelMapper:
    # Map Grid model names to ComfyUI workflow files
    DEFAULT_WORKFLOW_MAP = {
        # Video Generation Models
        "wan2_2_t2v_14b": "wan2.2_ti2v_5B",
        "wan2.2-t2v-a14b": "wan2.2_ti2v_5B",
        "wan2_2_t2v_14b_hq": "wan2.2_ti2v_5B",
        "wan2.2-t2v-a14b-hq": "wan2.2_ti2v_5B",
        "wan2_2_ti2v_5b": "wan2.2_ti2v_5B",
        "wan2.2_ti2v_5b": "wan2.2_ti2v_5B",
        "ltxv": "ltxv",
        
        # Flux Dev (all naming variants)
        "FLUX.1-dev": "flux1.dev",
        "flux.1-dev": "flux1.dev",
        "flux1-dev": "flux1.dev",
        "flux1_dev": "flux1.dev",
        "flux1.dev": "flux1.dev",
        
        # Flux Krea variants
        "flux.1-krea-dev": "flux1_krea_dev",
        "FLUX.1-krea-dev": "flux1_krea_dev",
        "flux1-krea-dev": "flux1_krea_dev",
        "flux1_krea_dev": "flux1_krea_dev",
        "krea": "krea",
        
        # Flux Kontext variants
        "FLUX.1-dev-Kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux.1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux_kontext_dev_basic": "flux_kontext_dev_basic",
        "flux1-kontext-dev": "flux_kontext_dev_basic",
        "flux1_kontext_dev": "flux_kontext_dev_basic",
        
        # Other image models
        "Chroma": "Chroma_final",
        "chroma_final": "Chroma_final",
        "chroma": "Chroma_final",
        "SDXL 1.0": "sdxl",
        "SDXL": "sdxl",
        "sdxl": "sdxl",
        "sdxl1": "sdxl1",
        "turbovision": "turbovision",
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

        logger.info(f"Initialized with {len(self.workflow_map)} model mappings")

    def _build_workflow_map(self):
        """Build mapping from Grid models to ComfyUI workflows"""
        self.workflow_map = {}
        from .config import Settings
        import os
        
        def resolve_case_insensitive(dir_path: str, filename: str) -> str:
            """Return absolute path to filename in dir_path, matched case-insensitively.
            Returns empty string if not found."""
            target = filename.lower()
            try:
                for fname in os.listdir(dir_path):
                    if fname.lower() == target:
                        return os.path.join(dir_path, fname)
            except FileNotFoundError:
                pass
            return ""
        
        # Copy default mappings but strip .json from workflow filenames
        for model, workflow_file in self.DEFAULT_WORKFLOW_MAP.items():
            # Add .json extension if not present when checking file existence
            filename = workflow_file if workflow_file.endswith('.json') else f"{workflow_file}.json"
            workflow_path = os.path.join(Settings.WORKFLOW_DIR, filename)
            if not os.path.exists(workflow_path):
                ci = resolve_case_insensitive(Settings.WORKFLOW_DIR, filename)
                workflow_path = ci or workflow_path
            if os.path.exists(workflow_path):
                # Store without .json extension
                self.workflow_map[model] = workflow_file
            else:
                logger.warning(f"Missing workflow file: {workflow_path}")

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

            logger.info(
                f"Loaded model reference from {'URL' if is_url else 'file'}: {location} (entries: {loaded_models})"
            )
        except Exception as e:
            logger.warning(f"Failed to load model reference: {e}")
        return reference_map

    def _iter_env_workflow_files(self) -> List[tuple[str, str]]:
        """Resolve workflow filenames from env settings.

        - WORKFLOW_FILE can be a single filename or comma-separated list
        - Files are resolved relative to Settings.WORKFLOW_DIR
        - Entries can be Grid model names (e.g. FLUX.1-dev) or raw workflow filenames
        """
        configured = Settings.WORKFLOW_FILE or ""
        workflow_filenames = [
            w.strip() for w in configured.split(",") if w and w.strip()
        ]
        resolved_paths: List[tuple[str, str]] = []
        for model_name in workflow_filenames:
            mapped_workflow = self.DEFAULT_WORKFLOW_MAP.get(model_name, model_name)
            if Settings.DEBUG:
                logger.debug(f"WORKFLOW_FILE entry '{model_name}' mapped to '{mapped_workflow}'")
            # Add .json extension if not present
            filename = mapped_workflow if mapped_workflow.endswith('.json') else f"{mapped_workflow}.json"
            abs_path = os.path.join(Settings.WORKFLOW_DIR, filename)
            if not os.path.exists(abs_path):
                # Case-insensitive fallback
                target = filename.lower()
                try:
                    for fname in os.listdir(Settings.WORKFLOW_DIR):
                        if fname.lower() == target:
                            abs_path = os.path.join(Settings.WORKFLOW_DIR, fname)
                            break
                except FileNotFoundError:
                    pass
            if os.path.exists(abs_path):
                resolved_paths.append((model_name, abs_path))
            else:
                logger.warning(f"Workflow file not found from env: {abs_path}")
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
            logger.warning(f"Failed to read workflow '{workflow_path}': {e}")
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
        
        Use explicit mapping for known workflow files to avoid model name resolution issues.
        """
        self.workflow_map = {}
        env_workflows = self._iter_env_workflow_files()
        
        # Direct mapping - workflow filenames now match model names exactly
        # Store model names without .json extension
        logger.info("Using simplified direct filename mapping")
        
        logger.info("Building workflow map from WORKFLOW_FILE env var")
        for grid_model_name, abs_path in env_workflows:
            filename = os.path.basename(abs_path)
            logger.debug(f"Processing workflow file: {filename}")
            
            # Direct mapping: filename without .json extension becomes workflow identifier
            if filename.endswith('.json'):
                workflow_id = filename[:-5]  # Remove .json extension
                self.workflow_map[grid_model_name] = workflow_id
                logger.info(f"Mapped {grid_model_name} -> {workflow_id}")
            else:
                logger.warning(f"Skipping non-JSON file: {filename}")
        
        logger.info(f"Final workflow map from env: {len(self.workflow_map)} models")
        for model, workflow in self.workflow_map.items():
            logger.debug(f"  {model} -> {workflow}")

    def get_workflow_file(self, horde_model_name: str) -> str:
        """Get the workflow file for a Grid model"""
        # Look up workflow for model
        
        # Direct lookup
        direct_match = self.workflow_map.get(horde_model_name)
        if direct_match:
            # Add .json extension
            return f"{direct_match}.json"
        
        # Partial match
        partial_match = next(
            (
                v
                for k, v in self.workflow_map.items()
                if horde_model_name.lower() in k.lower()
            ),
            None,
        )
        if partial_match:
            # Add .json extension
            return f"{partial_match}.json"
        
        # Fallback to defaults mapping (case-insensitive)
        lower_name = horde_model_name.lower()
        default_match = next(
            (v for k, v in self.DEFAULT_WORKFLOW_MAP.items() if k.lower() == lower_name),
            None,
        )
        if default_match:
            return default_match if default_match.endswith(".json") else f"{default_match}.json"
        
        # Last-resort default
        return "Dreamshaper.json"  # Default workflow

    def get_available_horde_models(self) -> List[str]:
        return list(self.workflow_map.keys())


model_mapper = ModelMapper()


async def initialize_model_mapper(comfy_url: str):
    await model_mapper.initialize(comfy_url)


def get_horde_models() -> List[str]:
    return model_mapper.get_available_horde_models()


def get_workflow_file(horde_model_name: str) -> str:
    return model_mapper.get_workflow_file(horde_model_name)
