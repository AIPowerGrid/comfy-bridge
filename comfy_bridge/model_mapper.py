import httpx  # type: ignore
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
        "wan2_2_t2v_14b": "wan2.2-t2v-a14b",
        "wan2.2-t2v-a14b": "wan2.2-t2v-a14b",
        "wan2_2_t2v_14b_hq": "wan2.2-t2v-a14b-hq",
        "wan2.2-t2v-a14b-hq": "wan2.2-t2v-a14b-hq",
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
        "flux1-krea-dev_fp8_scaled": "flux1-krea-dev_fp8_scaled",
        "FLUX.1-dev-Kontext-fp8-scaled": "flux1-krea-dev_fp8_scaled",
        "flux.1-dev-kontext-fp8-scaled": "flux1-krea-dev_fp8_scaled",
        "flux1-dev-kontext-fp8-scaled": "flux1-krea-dev_fp8_scaled",
        "flux1_dev_kontext_fp8_scaled": "flux1-krea-dev_fp8_scaled",
        "flux1_dev_kontext_fp8_scaled": "flux1-krea-dev_fp8_scaled",
        "flux1_dev_kontext_fp8_scaled": "flux1-krea-dev_fp8_scaled",
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
            # Validate workflows against available models
            await self._validate_workflows_against_models(comfy_url)
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
        Validates that required models are installed before advertising workflows.
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

    def _has_local_flux_assets(self) -> bool:
        """Fallback detection for Flux assets on disk when ComfyUI doesn't list them."""
        models_root = os.getenv("MODELS_PATH", "/app/ComfyUI/models")

        def dir_has_keywords(subdir: str, keywords: list[str]) -> bool:
            path = os.path.join(models_root, subdir)
            try:
                for fname in os.listdir(path):
                    lower = fname.lower()
                    if any(keyword in lower for keyword in keywords):
                        return True
            except FileNotFoundError:
                return False
            return False

        # Flux needs the unet weights plus clip_l, t5/t5xxl text encoder, and ae VAE
        unet_present = (
            dir_has_keywords("diffusion_models", ["flux"])
            or dir_has_keywords("unet", ["flux"])
            or dir_has_keywords("checkpoints", ["flux"])
        )
        clip_present = dir_has_keywords("clip", ["clip_l", "clip-l", "clip_l.safetensors"])
        text_encoder_present = dir_has_keywords("text_encoders", ["t5", "umt5"])
        vae_present = dir_has_keywords("vae", ["ae.safetensors", "ae"])

        return unet_present and clip_present and text_encoder_present and vae_present
    
    async def _validate_workflows_against_models(self, comfy_url: str):
        """Validate workflows against available models and remove incompatible ones.
        
        This ensures we only advertise models whose workflows have all required models installed.
        """
        # Import here to avoid circular imports
        from .workflow import detect_workflow_model_type, is_model_compatible
        from .comfyui_client import ComfyUIClient
        
        # Get available models from ComfyUI (may be empty if the API isn't providing loaders)
        comfy_client = ComfyUIClient(comfy_url)
        try:
            available_models = await comfy_client.get_available_models()
        except Exception as e:
            logger.warning(f"Failed to fetch available models for validation: {e}")
            logger.warning("Continuing without loader metadata; will rely on filesystem fallbacks")
            available_models = {}
        
        if not available_models:
            logger.warning("No loader metadata returned by /object_info – proceeding with empty lists and filesystem checks")
        
        # Validate each workflow in the map
        workflows_to_remove = []
        for grid_model_name, workflow_id in list(self.workflow_map.items()):
            workflow_path = os.path.join(Settings.WORKFLOW_DIR, f"{workflow_id}.json")
            
            if not os.path.exists(workflow_path):
                logger.warning(f"Workflow file not found: {workflow_path}")
                workflows_to_remove.append(grid_model_name)
                continue
            
            try:
                # Load workflow
                with open(workflow_path, "r", encoding="utf-8") as f:
                    workflow = json.load(f)
                
                # Detect workflow model type
                model_type = detect_workflow_model_type(workflow)
                
                if model_type == "unknown":
                    logger.debug(f"Workflow {workflow_id} has unknown type, allowing it (runtime checks will enforce requirements)")
                    continue
                
                has_compatible_models = False
                
                if model_type == "flux":
                    unet_models = available_models.get("UNETLoader") or []
                    dual_clip = available_models.get("DualCLIPLoader") or {}
                    vae_models = available_models.get("VAELoader") or []
                    
                    flux_unet = [m for m in unet_models if is_model_compatible(m, "flux")]
                    clip1 = dual_clip.get("clip_name1", []) if isinstance(dual_clip, dict) else []
                    clip2 = dual_clip.get("clip_name2", []) if isinstance(dual_clip, dict) else []
                    flux_clip1 = [m for m in clip1 if is_model_compatible(m, "flux")]
                    flux_clip2 = [m for m in clip2 if is_model_compatible(m, "flux")]
                    flux_vae = [m for m in vae_models if is_model_compatible(m, "flux")]
                    
                    has_compatible_models = bool(flux_unet and (flux_clip1 or flux_clip2) and flux_vae)
                    
                    if not has_compatible_models and self._has_local_flux_assets():
                        has_compatible_models = True
                        logger.debug(f"Flux workflow {workflow_id}: local flux assets detected, allowing despite missing loader metadata")
                
                elif model_type == "wanvideo":
                    # Some ComfyUI builds omit WanVideo loader info; require at least a VAE entry as a proxy.
                    vae_models = available_models.get("VAELoader") or []
                    if vae_models:
                        has_compatible_models = True
                    else:
                        logger.warning(f"WanVideo workflow {workflow_id}: no VAEs reported; allowing but runtime may still fail if models are absent")
                        has_compatible_models = True  # fall back to runtime validation
                
                else:
                    # For SDXL/other workflows, assume success if we reached here.
                    has_compatible_models = True
                
                if not has_compatible_models:
                    logger.warning(
                        f"Removing {grid_model_name} from advertised models: "
                        f"No compatible {model_type} loaders detected and no filesystem fallback available"
                    )
                    workflows_to_remove.append(grid_model_name)
                else:
                    logger.debug(f"Workflow {workflow_id} validated – compatible assets detected or fallback satisfied")
                    
            except Exception as e:
                logger.warning(f"Failed to validate workflow {workflow_id}: {e}")
                # On error, remove the workflow to be safe
                workflows_to_remove.append(grid_model_name)
        
        # Remove invalid workflows
        for model_name in workflows_to_remove:
            del self.workflow_map[model_name]
        
        if workflows_to_remove:
            logger.info(f"Removed {len(workflows_to_remove)} workflows due to missing models")

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
