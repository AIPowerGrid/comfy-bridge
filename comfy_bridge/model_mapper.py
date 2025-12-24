import httpx  # type: ignore
import json
import os
import logging
from typing import Dict, List, Optional

from .config import Settings
from .modelvault_client import get_modelvault_client, OnChainModelInfo, ModelType

logger = logging.getLogger(__name__)


def normalize_workflow_name(name: str) -> str:
    """Normalize workflow name by converting underscores to hyphens for consistency."""
    return name.replace("_", "-")


def find_workflow_file(workflow_dir: str, workflow_name: str) -> Optional[str]:
    """
    Find a workflow file by name, handling dash/underscore variations.
    
    Tries multiple variations:
    1. Exact match
    2. With underscores replaced by hyphens
    3. With hyphens replaced by underscores
    4. Case-insensitive versions of all above
    
    Returns the absolute path if found, None otherwise.
    """
    if not workflow_name:
        return None
    
    # Add .json extension if not present
    base_name = workflow_name[:-5] if workflow_name.endswith('.json') else workflow_name
    
    # Generate all variations to try
    variations = [
        base_name,                           # Original
        base_name.replace("_", "-"),         # Underscores to hyphens
        base_name.replace("-", "_"),         # Hyphens to underscores
    ]
    
    # Add .json extension to all variations
    filenames_to_try = [f"{v}.json" for v in variations]
    
    try:
        available_files = os.listdir(workflow_dir)
    except FileNotFoundError:
        return None
    
    # Create lowercase lookup map for case-insensitive matching
    file_map = {f.lower(): f for f in available_files}
    
    for filename in filenames_to_try:
        # Try exact match first
        full_path = os.path.join(workflow_dir, filename)
        if os.path.exists(full_path):
            return full_path
        
        # Try case-insensitive match
        actual_name = file_map.get(filename.lower())
        if actual_name:
            return os.path.join(workflow_dir, actual_name)
    
    return None


async def fetch_comfyui_models(comfy_url: str) -> List[str]:
    """Fetch available models from ComfyUI (for local availability check)."""
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

                    flux_loaders = ["FluxLoader", "UNETLoader", "DualCLIPLoader"]
                    flux_models = []
                    for loader_name in flux_loaders:
                        loader_data = data.get(loader_name, {})
                        if loader_data and loader_data.get("input", {}).get("required", {}).get("model_name"):
                            loader_models = (
                                loader_data
                                .get("input", {})
                                .get("required", {})
                                .get("model_name", [[]])[0]
                            )
                            flux_models.extend(loader_models)
                            break  # Use first available loader
                    models.extend(flux_models)
                elif endpoint == "/model_list":
                    models = data.get("checkpoints", []) + data.get("models", [])

                if models:
                    return models

            except Exception as e:
                # Only log warnings in debug mode to reduce noise
                pass

    return []


def get_chain_models() -> Dict[str, OnChainModelInfo]:
    """
    Get all registered models from the blockchain.
    
    The blockchain is the single source of truth for model registration.
    """
    client = get_modelvault_client(enabled=Settings.MODELVAULT_ENABLED)
    return client.fetch_all_models()


class ModelMapper:
    """
    Maps Grid model names to ComfyUI workflow files.
    
    Model registry is sourced from the blockchain (ModelVault contract).
    Workflow mappings are derived from on-chain model data.
    """
    
    # Fallback workflow mappings for models not yet on-chain or for legacy support
    # Map BOTH the Grid API model names (lowercase) AND stable_diffusion.json names
    FALLBACK_WORKFLOW_MAP = {
        # Video Generation Models - map all variants to workflow files
        # Grid API uses lowercase underscore names for job requests
        "wan2_2_t2v_14b": "wan2.2-t2v-a14b",       # Grid API name
        "wan2.2-t2v-a14b": "wan2.2-t2v-a14b",      # stable_diffusion.json name
        "wan2_2_t2v_14b_hq": "wan2.2-t2v-a14b-hq", # Grid API name
        "wan2.2-t2v-a14b-hq": "wan2.2-t2v-a14b-hq",# stable_diffusion.json name
        "wan2_2_t2v_14b_best": "wan2.2-t2v-a14b-best",
        "wan2.2-t2v-a14b-best": "wan2.2-t2v-a14b-best",
        "wan2_2_ti2v_5b": "wan2.2_ti2v_5B",        # Grid API name (lowercase b!)
        "wan2.2_ti2v_5B": "wan2.2_ti2v_5B",        # stable_diffusion.json name (uppercase B)
        "wan2.2_ti2v_5b": "wan2.2_ti2v_5B",        # lowercase variant
        "ltxv": "ltxv",
        
        # Flux Dev (all naming variants)
        "FLUX.1-dev": "flux1.dev",
        "flux.1-dev": "flux1.dev",
        "flux1-dev": "flux1.dev",
        "flux1_dev": "flux1.dev",
        "flux1.dev": "flux1.dev",
        
        # Flux Krea variants - workflow file is flux.1-krea-dev.json
        "flux.1-krea-dev": "flux.1-krea-dev",
        "FLUX.1-krea-dev": "flux.1-krea-dev",
        "flux1-krea-dev": "flux.1-krea-dev",
        "flux1_krea_dev": "flux.1-krea-dev",
        "krea": "flux.1-krea-dev",
        
        # Flux Kontext variants - workflow file is FLUX.1-dev-Kontext-fp8-scaled.json
        "flux1-krea-dev_fp8_scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "FLUX.1-dev-Kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux.1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux1_dev_kontext_fp8_scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux_kontext_dev_basic": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux1-kontext-dev": "FLUX.1-dev-Kontext-fp8-scaled",
        "flux1_kontext_dev": "FLUX.1-dev-Kontext-fp8-scaled",
        
        # Other image models - workflow file is Chroma_final.json
        "Chroma": "Chroma_final",
        "chroma_final": "Chroma_final",
        "chroma": "Chroma_final",
        # SDXL - workflow file is sdxl1.json
        "SDXL 1.0": "sdxl1",
        "SDXL": "sdxl1",
        "sdxl": "sdxl1",
        "sdxl1": "sdxl1",
        "turbovision": "turbovision",
    }
    
    # Keep DEFAULT_WORKFLOW_MAP as alias for backwards compatibility
    DEFAULT_WORKFLOW_MAP = FALLBACK_WORKFLOW_MAP

    def __init__(self):
        self.available_models: List[str] = []
        # Maps Grid model name -> workflow filename
        self.workflow_map: Dict[str, str] = {}
        # On-chain model registry (blockchain is source of truth)
        self.chain_models: Dict[str, OnChainModelInfo] = {}

    async def initialize(self, comfy_url: str):
        """
        Initialize the model mapper.
        
        Loads model registry from blockchain first, then validates
        against locally available models and workflows.
        """
        # Get models available in Comfy (for local availability check)
        self.available_models = await fetch_comfyui_models(comfy_url)

        # Load model registry from blockchain (source of truth)
        self._load_chain_models()

        # If WORKFLOW_FILE is set, only use models derived from those workflows
        if Settings.WORKFLOW_FILE:
            self._build_workflow_map_from_env()
            # Validate workflows against available models
            await self._validate_workflows_against_models(comfy_url)
        else:
            # Build workflow map from chain data + fallbacks
            self._build_workflow_map()

        logger.info(f"Initialized with {len(self.workflow_map)} model mappings (chain: {len(self.chain_models)} models)")

    def _load_chain_models(self):
        """Load model registry from the blockchain."""
        try:
            self.chain_models = get_chain_models()
            logger.info(f"Loaded {len(self.chain_models)} models from blockchain")
        except Exception as e:
            logger.warning(f"Failed to load models from blockchain: {e}")
            self.chain_models = {}

    def _build_workflow_map(self):
        """
        Build mapping from Grid models to ComfyUI workflows.
        
        Primary source: blockchain model registry
        Fallback: FALLBACK_WORKFLOW_MAP for models not yet on-chain
        """
        self.workflow_map = {}
        from .config import Settings
        import os
        
        def check_workflow_exists(workflow_file: str) -> bool:
            """Check if workflow file exists (handles dash/underscore/case variations)."""
            return find_workflow_file(Settings.WORKFLOW_DIR, workflow_file) is not None
        
        # 1. Build workflow mappings from blockchain models (primary source)
        for model_name, model_info in self.chain_models.items():
            # Derive workflow from model's display_name or architecture
            workflow_id = self._derive_workflow_from_chain_model(model_info)
            if workflow_id and check_workflow_exists(workflow_id):
                self.workflow_map[model_info.display_name] = workflow_id
                # Also add common variants
                if model_info.file_name:
                    self.workflow_map[model_info.file_name] = workflow_id
                model_id = model_info.get_model_id()
                if model_id:
                    self.workflow_map[model_id] = workflow_id
                logger.debug(f"Chain model {model_info.display_name} -> workflow {workflow_id}")
        
        # 2. Add fallback mappings for models not yet on-chain
        for model, workflow_file in self.FALLBACK_WORKFLOW_MAP.items():
            if model not in self.workflow_map and check_workflow_exists(workflow_file):
                self.workflow_map[model] = workflow_file
                logger.debug(f"Fallback mapping {model} -> workflow {workflow_file}")
            elif model not in self.workflow_map:
                logger.warning(f"Missing workflow file for fallback model: {model}")
        
        logger.info(f"Built workflow map: {len(self.workflow_map)} mappings ({len(self.chain_models)} from chain)")

    def _derive_workflow_from_chain_model(self, model_info: OnChainModelInfo) -> Optional[str]:
        """
        Derive the workflow filename from on-chain model data.
        
        Uses model type, architecture, and display_name to determine workflow.
        """
        display_name = model_info.display_name
        model_type = model_info.model_type
        architecture = model_info.architecture.lower() if model_info.architecture else ""
        
        # Check if there's a direct mapping in fallbacks first (for known models)
        for fallback_name, workflow in self.FALLBACK_WORKFLOW_MAP.items():
            if fallback_name.lower() == display_name.lower():
                return workflow
        
        # Derive based on model type
        if model_type == ModelType.VIDEO:
            # Video models - check for WAN variants
            if "wan" in display_name.lower():
                if "ti2v" in display_name.lower() or "i2v" in display_name.lower():
                    return "wan2.2_ti2v_5B"
                elif "hq" in display_name.lower():
                    return "wan2.2-t2v-a14b-hq"
                else:
                    return "wan2.2-t2v-a14b"
            elif "ltxv" in display_name.lower():
                return "ltxv"
        
        elif model_type == ModelType.FLUX:
            # FLUX models
            if "kontext" in display_name.lower():
                return "flux_kontext_dev_basic"
            elif "krea" in display_name.lower():
                return "flux1_krea_dev"
            elif "chroma" in display_name.lower():
                return "Chroma_final"
            else:
                return "flux1.dev"
        
        elif model_type == ModelType.SDXL:
            return "sdxl"
        
        elif model_type == ModelType.SD15:
            return None  # SD1.5 models not supported - don't default
        
        # Default: try to match display_name directly to workflow file
        normalized = display_name.replace(" ", "_").replace(".", "_").replace("-", "_")
        return normalized

    def _iter_env_workflow_files(self) -> List[tuple[str, str]]:
        """Resolve workflow filenames from env settings.

        - WORKFLOW_FILE can be a single filename or comma-separated list
        - Files are resolved relative to Settings.WORKFLOW_DIR
        - Entries can be Grid model names (e.g. FLUX.1-dev) or raw workflow filenames
        - Chain-registered models take priority for workflow resolution
        """
        configured = Settings.WORKFLOW_FILE or ""
        workflow_filenames = [
            w.strip() for w in configured.split(",") if w and w.strip()
        ]
        resolved_paths: List[tuple[str, str]] = []
        for model_name in workflow_filenames:
            # First check if model is registered on chain
            chain_model = self.chain_models.get(model_name)
            if chain_model:
                mapped_workflow = self._derive_workflow_from_chain_model(chain_model)
                if Settings.DEBUG:
                    logger.debug(f"WORKFLOW_FILE entry '{model_name}' mapped from chain to '{mapped_workflow}'")
            else:
                # Fallback to static mapping
                mapped_workflow = self.FALLBACK_WORKFLOW_MAP.get(model_name, model_name)
                if Settings.DEBUG:
                    logger.debug(f"WORKFLOW_FILE entry '{model_name}' mapped from fallback to '{mapped_workflow}'")
            
            if not mapped_workflow:
                mapped_workflow = model_name
            
            # Use find_workflow_file which handles dash/underscore normalization
            abs_path = find_workflow_file(Settings.WORKFLOW_DIR, mapped_workflow)
            if abs_path:
                resolved_paths.append((model_name, abs_path))
            else:
                logger.warning(f"Workflow file not found for '{model_name}' (tried: {mapped_workflow} with dash/underscore variants)")
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
        """
        Resolve a file name to a Grid model name.
        
        Looks up in chain-registered models first.
        """
        # Check chain models by file_name
        for model_info in self.chain_models.values():
            if model_info.file_name == file_name:
                return model_info.display_name
        
        # Partial match on file_name
        file_lower = file_name.lower()
        for model_info in self.chain_models.values():
            if model_info.file_name and file_lower in model_info.file_name.lower():
                return model_info.display_name
        
        return None

    # Reverse mapping: workflow filename -> Grid model name
    # These MUST match names that exist in stable_diffusion.json
    # Check: https://raw.githubusercontent.com/AIPowerGrid/grid-image-model-reference/main/stable_diffusion.json
    WORKFLOW_TO_GRID_MODEL = {
        # Video Generation Models - EXACT names from stable_diffusion.json
        "wan2.2-t2v-a14b": "wan2.2-t2v-a14b",       # Use hyphen version (canonical)
        "wan2.2-t2v-a14b-hq": "wan2.2-t2v-a14b-hq", # Use hyphen version (canonical)
        "wan2.2-t2v-a14b-best": "wan2.2-t2v-a14b-best",
        "wan2.2_ti2v_5B": "wan2.2_ti2v_5B",         # Both variants exist
        "wan2.2-ti2v-5B": "wan2.2_ti2v_5B",         # Map hyphen to underscore variant
        "ltxv": "ltxv",
        
        # Flux Dev - ONLY use FLUX.1-dev (with dot), NOT flux1.dev
        "flux1.dev": "FLUX.1-dev",
        "FLUX.1-dev": "FLUX.1-dev",
        "flux1-dev": "FLUX.1-dev",
        
        # Flux Krea - use exact stable_diffusion.json name
        "flux.1-krea-dev": "flux.1-krea-dev",
        "krea": "flux.1-krea-dev",
        
        # Flux Kontext - use exact stable_diffusion.json name
        "FLUX.1-dev-Kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
        
        # Other image models
        "Chroma_final": "Chroma",
        "Chroma": "Chroma",
        "sdxl1": "SDXL 1.0",
        "SDXL": "SDXL 1.0",
    }

    # Map workflow IDs to Grid model names that MUST exist in stable_diffusion.json
    # These are the ONLY names the API will accept - check:
    # https://raw.githubusercontent.com/AIPowerGrid/grid-image-model-reference/main/stable_diffusion.json
    WORKFLOW_TO_ALL_GRID_NAMES = {
        # WAN Video models - use EXACT names from stable_diffusion.json
        "wan2.2_ti2v_5B": ["wan2.2_ti2v_5B", "wan2_2_ti2v_5b"],  # Both are in stable_diffusion.json
        "wan2.2-t2v-a14b": ["wan2.2-t2v-a14b"],     # Only hyphen version exists in stable_diffusion.json
        "wan2.2-t2v-a14b-hq": ["wan2.2-t2v-a14b-hq"],  # Only hyphen version exists
        
        # FLUX models - use EXACT names from stable_diffusion.json
        "flux.1-krea-dev": ["flux.1-krea-dev"],
        "FLUX.1-dev-Kontext-fp8-scaled": ["FLUX.1-dev-Kontext-fp8-scaled"],
        "flux1.dev": ["FLUX.1-dev"],               # Only FLUX.1-dev exists, NOT flux1.dev
        "FLUX.1-dev": ["FLUX.1-dev"],              # Canonical name
        
        # Other models
        "Chroma_final": ["Chroma"],
        "sdxl1": ["SDXL 1.0"],
        "ltxv": ["ltxv"],
    }

    def _build_workflow_map_from_env(self):
        """Build workflow map based on env-specified workflows.
        
        Use explicit mapping for known workflow files to avoid model name resolution issues.
        Validates that required models are installed before advertising workflows.
        Advertises ALL naming variants for models to catch jobs from any source.
        """
        self.workflow_map = {}
        env_workflows = self._iter_env_workflow_files()
        
        logger.info("Building workflow map from WORKFLOW_FILE env var")
        for raw_entry, abs_path in env_workflows:
            filename = os.path.basename(abs_path)
            logger.debug(f"Processing workflow file: {filename}")
            
            if filename.endswith('.json'):
                workflow_id = filename[:-5]  # Remove .json extension
                
                # Check if this workflow has multiple Grid name variants
                all_names = self.WORKFLOW_TO_ALL_GRID_NAMES.get(workflow_id)
                if all_names:
                    # Register ALL name variants for this workflow
                    for grid_model_name in all_names:
                        self.workflow_map[grid_model_name] = workflow_id
                        logger.info(f"Mapped Grid model '{grid_model_name}' -> workflow '{workflow_id}'")
                else:
                    # Single name from WORKFLOW_TO_GRID_MODEL or use workflow_id
                    grid_model_name = self.WORKFLOW_TO_GRID_MODEL.get(workflow_id, workflow_id)
                    
                    # Also check if raw entry maps to a grid model name
                    if raw_entry.endswith('.json'):
                        raw_workflow = raw_entry[:-5]
                    else:
                        raw_workflow = raw_entry
                    grid_from_raw = self.WORKFLOW_TO_GRID_MODEL.get(raw_workflow)
                    if grid_from_raw:
                        grid_model_name = grid_from_raw
                    
                    self.workflow_map[grid_model_name] = workflow_id
                    logger.info(f"Mapped Grid model '{grid_model_name}' -> workflow '{workflow_id}'")
            else:
                logger.warning(f"Skipping non-JSON file: {filename}")
        
        logger.info(f"🗺️ FINAL WORKFLOW MAP from env: {len(self.workflow_map)} model(s)")
        logger.info(f"   These are the EXACT model names we will advertise to the Grid API:")
        for model, workflow in self.workflow_map.items():
            logger.info(f"   📍 '{model}' -> workflow '{workflow}.json'")

    def _has_local_flux_assets(self) -> bool:
        """Fallback detection for Flux assets on disk when ComfyUI doesn't list them."""
        # Check multiple possible model locations
        models_root = os.getenv("MODELS_PATH")
        if not models_root or not os.path.isdir(models_root):
            for path in ["/app/ComfyUI/models", "/persistent_volumes/models"]:
                if os.path.isdir(path):
                    models_root = path
                    break
            else:
                models_root = "/app/ComfyUI/models"

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
                    # Check for FluxLoader first (newer FLUX implementations)
                    flux_loader_models = available_models.get("FluxLoader") or []

                    if flux_loader_models:
                        # If FluxLoader is available, use it
                        has_compatible_models = True
                        logger.debug(f"Flux workflow {workflow_id}: FluxLoader detected")
                    else:
                        # Fall back to individual component loaders
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

                    # Allow FLUX models even without detected loaders - runtime will handle it
                    if not has_compatible_models:
                        logger.warning(f"Flux workflow {workflow_id}: No compatible loaders detected, allowing anyway (runtime validation will apply)")
                        has_compatible_models = True

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

    def get_workflow_file(self, horde_model_name: str) -> Optional[str]:
        """Get the workflow file for a Grid model.
        
        Returns the actual filename found on disk, handling dash/underscore variations.
        """
        from .config import Settings
        
        # Try to find workflow file for each potential match
        candidates = []
        
        # Direct lookup
        direct_match = self.workflow_map.get(horde_model_name)
        if direct_match:
            candidates.append(direct_match)
        
        # Check chain models for dynamic resolution
        chain_model = self.chain_models.get(horde_model_name)
        if chain_model:
            workflow = self._derive_workflow_from_chain_model(chain_model)
            if workflow:
                candidates.append(workflow)
        
        # Partial match
        partial_match = next(
            (v for k, v in self.workflow_map.items() if horde_model_name.lower() in k.lower()),
            None,
        )
        if partial_match:
            candidates.append(partial_match)
        
        # Fallback to defaults mapping (case-insensitive)
        lower_name = horde_model_name.lower()
        default_match = next(
            (v for k, v in self.FALLBACK_WORKFLOW_MAP.items() if k.lower() == lower_name),
            None,
        )
        if default_match:
            candidates.append(default_match)
        
        # Try to find each candidate file (with dash/underscore normalization)
        for candidate in candidates:
            found_path = find_workflow_file(Settings.WORKFLOW_DIR, candidate)
            if found_path:
                # Return just the filename, not the full path
                return os.path.basename(found_path)
        
        # No fallback - return None if no workflow found
        logger.warning(f"No workflow found for model '{horde_model_name}' - model will not be advertised")
        return None

    def get_available_horde_models(self) -> List[str]:
        """Get list of available models (only installed models with workflows).
        
        Only returns models that have configured workflows - not all models
        from the blockchain. This ensures we only advertise what we can serve.
        """
        # Only return models that have workflow mappings (i.e., are installed)
        models = list(self.workflow_map.keys())
        logger.debug(f"get_available_horde_models() returning: {models}")
        return models

    def is_model_on_chain(self, model_name: str) -> bool:
        """Check if a model is registered on the blockchain."""
        return model_name in self.chain_models
    
    def get_chain_model_info(self, model_name: str) -> Optional[OnChainModelInfo]:
        """Get on-chain model info if registered."""
        return self.chain_models.get(model_name)


model_mapper = ModelMapper()


async def initialize_model_mapper(comfy_url: str):
    """Initialize the model mapper with chain data and local models."""
    await model_mapper.initialize(comfy_url)


def get_horde_models() -> List[str]:
    """Get list of all available models."""
    return model_mapper.get_available_horde_models()


def get_workflow_validated_models() -> set:
    """Get set of models that have valid workflow files.
    
    These models passed workflow validation and should be trusted even if 
    traditional health checks fail (e.g., API-based models like ltxv).
    """
    return set(model_mapper.workflow_map.keys())


def get_workflow_file(horde_model_name: str) -> Optional[str]:
    """Get workflow file for a model. Returns None if no workflow found."""
    return model_mapper.get_workflow_file(horde_model_name)


def is_model_registered_on_chain(model_name: str) -> bool:
    """Check if a model is registered on the blockchain."""
    return model_mapper.is_model_on_chain(model_name)


def get_chain_model(model_name: str) -> Optional[OnChainModelInfo]:
    """Get on-chain model info if registered."""
    return model_mapper.get_chain_model_info(model_name)


def refresh_chain_models():
    """Refresh the model registry from blockchain."""
    client = get_modelvault_client(enabled=Settings.MODELVAULT_ENABLED)
    client.refresh_cache()
    model_mapper.chain_models = client.fetch_all_models()
