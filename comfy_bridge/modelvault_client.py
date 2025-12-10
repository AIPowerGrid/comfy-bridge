"""
ModelVault Client - On-chain model registry for the comfy-bridge.
The blockchain is the SINGLE source of truth for registered models.
Queries the ModelVault contract on Base Sepolia for model discovery, validation, and downloads.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)

import os

MODELVAULT_CONTRACT_ADDRESS = os.getenv("MODELVAULT_CONTRACT", "0xe660455D4A83bbbbcfDCF4219ad82447a831c8A1")
MODELVAULT_RPC_URL = os.getenv("MODELVAULT_RPC_URL", "https://sepolia.base.org")
MODELVAULT_CHAIN_ID = 84532

# Alias map: user-friendly names -> blockchain-registered names
# This allows users to request models using familiar naming conventions
MODEL_NAME_ALIASES = {
    # WAN 2.2 Text-to-Video models - maps to catalog names
    "wan2_2_t2v_14b": "wan2.2-t2v-a14b",
    "wan2.2_t2v_a14b": "wan2.2-t2v-a14b",
    "wan2.2_t2v_14b": "wan2.2-t2v-a14b",
    "wan-2.2-t2v-14b": "wan2.2-t2v-a14b",
    "wan2.2-t2v-14b": "wan2.2-t2v-a14b",
    
    # WAN 2.2 Text-to-Video HQ models
    "wan2_2_t2v_14b_hq": "wan2.2-t2v-a14b-hq",
    "wan2.2_t2v_a14b_hq": "wan2.2-t2v-a14b-hq",
    "wan2.2_t2v_14b_hq": "wan2.2-t2v-a14b-hq",
    "wan2.2-t2v-14b-hq": "wan2.2-t2v-a14b-hq",
    
    # WAN 2.2 Text/Image-to-Video 5B models  
    "wan2_2_ti2v_5b": "wan2.2_ti2v_5B",
    "wan2.2-ti2v-5b": "wan2.2_ti2v_5B",
    "wan2.2-i2v-5b": "wan2.2_ti2v_5B",
    
    # FLUX models
    "flux.1-dev": "FLUX.1-dev",
    "flux1-dev": "FLUX.1-dev",
    "flux1.dev": "FLUX.1-dev",
    "flux1_dev": "FLUX.1-dev",
    
    # FLUX Kontext
    "flux.1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
    "flux1-dev-kontext-fp8-scaled": "FLUX.1-dev-Kontext-fp8-scaled",
    "flux1_dev_kontext_fp8_scaled": "FLUX.1-dev-Kontext-fp8-scaled",
    
    # FLUX Krea
    "flux.1-krea-dev": "flux.1-krea-dev",
    "flux1-krea-dev": "flux.1-krea-dev",
    "flux1_krea_dev": "flux.1-krea-dev",
    
    # Other models
    "sdxl": "SDXL 1.0",
    "sdxl1": "SDXL 1.0",
    "sdxl1.0": "SDXL 1.0",
    "sdxl_1_0": "SDXL 1.0",
    "chroma": "Chroma",
}


class ModelType(IntEnum):
    TEXT_MODEL = 0   # LLM/Text generation
    IMAGE_MODEL = 1  # Image generation (SD, SDXL, FLUX)
    VIDEO_MODEL = 2  # Video generation (WAN, LTX)

    def to_workflow_type(self) -> str:
        """Convert model type to workflow type string."""
        mapping = {
            ModelType.TEXT_MODEL: "text",
            ModelType.IMAGE_MODEL: "image",
            ModelType.VIDEO_MODEL: "video",
        }
        return mapping.get(self, "unknown")


@dataclass
class ModelFile:
    """A downloadable file for a model."""
    file_name: str
    file_type: str  # checkpoint, vae, text_encoder, lora, etc.
    download_url: str
    mirror_url: str = ""
    sha256_hash: str = ""
    size_bytes: int = 0


@dataclass
class ModelConstraints:
    steps_min: int
    steps_max: int
    cfg_min: float
    cfg_max: float
    clip_skip: int
    allowed_samplers: List[str]
    allowed_schedulers: List[str]


@dataclass
class OnChainModelInfo:
    """Complete model information from the blockchain."""
    model_hash: str
    model_type: ModelType
    file_name: str
    display_name: str
    description: str
    is_nsfw: bool
    size_bytes: int
    inpainting: bool
    img2img: bool
    controlnet: bool
    lora: bool
    base_model: str
    architecture: str
    is_active: bool
    # Download files (from V2 contract or fallback)
    files: List[ModelFile] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    # Extended fields for workflow mapping (derived from on-chain data)
    workflow_id: str = ""
    
    def __post_init__(self):
        """Derive workflow_id from display_name if not set."""
        if not self.workflow_id:
            # Use display_name as workflow identifier, normalized
            self.workflow_id = self.display_name.lower().replace(" ", "_").replace(".", "_")
    
    def get_model_id(self) -> str:
        """Get the model identifier (filename without extension)."""
        return self.file_name.replace(".safetensors", "").replace(".ckpt", "").replace(".pt", "")
    
    def get_download_url(self, file_type: str = "checkpoint") -> Optional[str]:
        """Get download URL for a specific file type."""
        for f in self.files:
            if f.file_type == file_type:
                return f.download_url
        # Fallback to first file
        if self.files:
            return self.files[0].download_url
        return None


@dataclass
class ValidationResult:
    is_valid: bool
    reason: Optional[str] = None


# ABI matching ModelRegistry.sol (V1) deployed at 0xe660455D4A83bbbbcfDCF4219ad82447a831c8A1
# V1 contract struct: modelHash, modelType, fileName, name, description, isNSFW, 
#                     sizeBytes, timestamp, creator, inpainting, img2img, controlnet,
#                     lora, baseModel, architecture (NO isActive field)
MODEL_REGISTRY_ABI = [
    {
        "inputs": [{"name": "modelHash", "type": "bytes32"}],
        "name": "isModelExists",
        "outputs": [{"type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "modelHash", "type": "bytes32"}],
        "name": "getModelByHash",
        "outputs": [
            {
                "components": [
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "modelType", "type": "uint8"},
                    {"name": "fileName", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "isNSFW", "type": "bool"},
                    {"name": "sizeBytes", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "creator", "type": "address"},
                    {"name": "inpainting", "type": "bool"},
                    {"name": "img2img", "type": "bool"},
                    {"name": "controlnet", "type": "bool"},
                    {"name": "lora", "type": "bool"},
                    {"name": "baseModel", "type": "string"},
                    {"name": "architecture", "type": "string"},
                ],
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getAllModelHashes",
        "outputs": [{"type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalModels",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ModelVaultClient:
    """
    Client for querying the ModelVault contract on Base Sepolia.
    
    The blockchain is the single source of truth for model registration.
    All model discovery and validation flows through this client.
    """

    def __init__(
        self,
        rpc_url: str = MODELVAULT_RPC_URL,
        contract_address: str = MODELVAULT_CONTRACT_ADDRESS,
        enabled: bool = True,
    ):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.enabled = enabled
        self._web3 = None
        self._contract = None
        # Cache for model data (refreshed on demand)
        self._model_cache: Dict[str, OnChainModelInfo] = {}
        self._cache_initialized = False
        self._is_v2_contract = False  # Detect if contract has V2 features

        if enabled:
            self._init_web3()

    def _init_web3(self):
        """Initialize web3 connection lazily."""
        try:
            from web3 import Web3

            self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self._contract = self._web3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=MODEL_REGISTRY_ABI,
            )
            logger.info(f"ModelVault client initialized (chain: Base Sepolia, contract: {self.contract_address[:10]}...)")
            
            # Try to detect if this is a V2 contract
            self._detect_contract_version()
        except ImportError:
            logger.warning("web3 package not installed. ModelVault validation disabled. Install with: pip install web3")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize ModelVault client: {e}")
            self.enabled = False

    def _detect_contract_version(self):
        """Detect contract version. Currently only V1 is deployed."""
        # V1 contract is deployed at 0xe660455D4A83bbbbcfDCF4219ad82447a831c8A1
        self._is_v2_contract = False
        logger.info("ModelVault V1 contract (no on-chain download URLs)")

    @staticmethod
    def hash_model(file_name: str) -> bytes:
        """Generate model hash from filename (keccak256)."""
        from web3 import Web3

        return Web3.keccak(text=file_name)

    def is_model_registered(self, file_name: str) -> bool:
        """Check if a model is registered on-chain."""
        if not self.enabled or not self._contract:
            return True  # Permissive when disabled

        try:
            model_hash = self.hash_model(file_name)
            return self._contract.functions.isModelExists(model_hash).call()
        except Exception as e:
            logger.error(f"Error checking model registration: {e}")
            return True  # Permissive on error

    def get_model(self, file_name: str) -> Optional[OnChainModelInfo]:
        """Get model info from chain by filename."""
        if not self.enabled or not self._contract:
            return None

        try:
            model_hash = self.hash_model(file_name)
            return self.get_model_by_hash(model_hash)
        except Exception as e:
            logger.debug(f"Model not found on chain: {file_name} ({e})")
            return None

    def get_model_by_hash(self, model_hash: bytes) -> Optional[OnChainModelInfo]:
        """Get model info from chain by hash directly."""
        if not self.enabled or not self._contract:
            return None

        try:
            result = self._contract.functions.getModelByHash(model_hash).call()
            # V1 Contract struct order:
            # [0] modelHash, [1] modelType, [2] fileName, [3] name, [4] description,
            # [5] isNSFW, [6] sizeBytes, [7] timestamp, [8] creator, [9] inpainting,
            # [10] img2img, [11] controlnet, [12] lora, [13] baseModel, [14] architecture
            
            model_info = OnChainModelInfo(
                model_hash=result[0].hex(),
                model_type=ModelType(result[1]),
                file_name=result[2],
                display_name=result[3],
                description=result[4],
                is_nsfw=result[5],
                size_bytes=result[6],
                # result[7] is timestamp, result[8] is creator - skipped
                inpainting=result[9],
                img2img=result[10],
                controlnet=result[11],
                lora=result[12],
                base_model=result[13],
                architecture=result[14],
                is_active=True,  # V1 has no isActive, assume all are active
            )
            
            return model_info
        except Exception as e:
            logger.error(f"Error fetching model by hash: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _get_model_files(self, model_hash: bytes) -> List[ModelFile]:
        """Get download files for a model. V1 contract doesn't have on-chain download URLs."""
        # V1 contract doesn't store download URLs on-chain
        # Download URLs need to be provided via off-chain configuration
        return []
    
    def _infer_file_type_from_url(self, url: str) -> str:
        """Infer file type from download URL path."""
        if not url:
            return ""
        url_lower = url.lower()
        if "/diffusion_models/" in url_lower or "/unet/" in url_lower:
            return "diffusion_models"
        if "/vae/" in url_lower:
            return "vae"
        if "/text_encoders/" in url_lower or "/clip/" in url_lower:
            return "text_encoders"
        if "/loras/" in url_lower or "/lora/" in url_lower:
            return "lora"
        if "/checkpoints/" in url_lower or "/ckpt/" in url_lower:
            return "checkpoint"
        return ""
    
    def _infer_file_type_from_filename(self, filename: str) -> str:
        """Infer file type from filename patterns."""
        if not filename:
            return ""
        name_lower = filename.lower()
        # VAE patterns
        if "_vae" in name_lower or "vae_" in name_lower or name_lower.startswith("vae"):
            return "vae"
        # Text encoder patterns  
        if "umt5" in name_lower or "t5xxl" in name_lower or "clip" in name_lower:
            return "text_encoders"
        # LoRA patterns
        if "_lora" in name_lower or "lora_" in name_lower:
            return "lora"
        # Diffusion model patterns (WAN, etc.)
        if "_noise_" in name_lower or "t2v_" in name_lower or "ti2v_" in name_lower or "i2v_" in name_lower:
            return "diffusion_models"
        return ""

    def _load_fallback_download_urls(self, model_name: str) -> List[ModelFile]:
        """Load download URLs from local reference files for V1 contract fallback."""
        import json
        import os
        
        files = []
        
        # Try multiple possible paths for the model reference repository
        ref_path = os.environ.get("GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH", "")
        
        # Build list of possible catalog paths
        catalog_paths = []
        
        if ref_path:
            catalog_paths.append(os.path.join(ref_path, "stable_diffusion.json"))
        
        # Docker paths
        catalog_paths.extend([
            "/app/grid-image-model-reference/stable_diffusion.json",
            "/app/comfy-bridge/model_configs.json",
        ])
        
        # Auto-detect relative to this file's location (for local development)
        this_dir = os.path.dirname(os.path.abspath(__file__))
        comfy_bridge_root = os.path.dirname(this_dir)
        dev_root = os.path.dirname(comfy_bridge_root)
        
        catalog_paths.extend([
            os.path.join(dev_root, "grid-image-model-reference", "stable_diffusion.json"),
            os.path.join(comfy_bridge_root, "model_configs.json"),
        ])
        
        # Normalize model name for matching
        name_variants = [
            model_name,
            model_name.lower(),
            model_name.replace("-", "_"),
            model_name.replace("_", "-"),
            model_name.replace(".", "_"),
            model_name.lower().replace("-", "_"),
            model_name.lower().replace("_", "-"),
        ]
        
        for catalog_path in catalog_paths:
            try:
                if not os.path.exists(catalog_path):
                    continue
                    
                with open(catalog_path, 'r') as f:
                    catalog = json.load(f)
                
                # Search for model in catalog
                for name, data in catalog.items():
                    name_lower = name.lower()
                    if any(v.lower() == name_lower or v.lower() in name_lower or name_lower in v.lower() for v in name_variants):
                        # Found matching model, extract files and download info
                        config = data.get("config", {})
                        model_files = config.get("files", []) or data.get("files", [])
                        download_info = config.get("download", [])
                        
                        # Get config-level download URL as fallback
                        config_download_url = (
                            config.get("download_url") or 
                            config.get("file_url") or 
                            data.get("download_url") or
                            data.get("url") or
                            ""
                        )
                        
                        # Build maps of file_name -> download_url and file_name -> type from download array
                        download_urls = {}
                        download_types = {}
                        for dl in download_info:
                            if isinstance(dl, dict):
                                fn = dl.get("file_name", "")
                                url = dl.get("file_url") or dl.get("download_url") or dl.get("url", "")
                                file_type = dl.get("type", "")
                                if fn:
                                    if url:
                                        download_urls[fn] = url
                                    if file_type:
                                        download_types[fn] = file_type
                        
                        for file_info in model_files:
                            if isinstance(file_info, dict):
                                file_path = file_info.get("path", "")
                                # Get URL from file_info first, then fall back to download_urls map, then config-level URL
                                url = (
                                    file_info.get("url") or 
                                    file_info.get("file_url") or 
                                    file_info.get("download_url") or
                                    download_urls.get(file_path, "") or
                                    config_download_url
                                )
                                # Get type from file_info first, then from download_types map, then infer from URL
                                file_type = (
                                    file_info.get("type") or 
                                    download_types.get(file_path, "") or
                                    self._infer_file_type_from_url(url) or
                                    self._infer_file_type_from_filename(file_path) or
                                    "checkpoint"
                                )
                                
                                files.append(ModelFile(
                                    file_name=file_path,
                                    file_type=file_type,
                                    download_url=url,
                                    mirror_url=file_info.get("mirror_url", ""),
                                    sha256_hash=file_info.get("sha256") or file_info.get("sha256sum", ""),
                                    size_bytes=int(file_info.get("size_bytes", 0) or 0),
                                ))
                        
                        if files:
                            logger.info(f"Found {len(files)} download URL(s) for {model_name} from {catalog_path}")
                            return files
            except Exception as e:
                logger.debug(f"Could not load catalog {catalog_path}: {e}")
                continue
        
        return files

    def get_constraints(self, model_id: str) -> Optional[ModelConstraints]:
        """Get model constraints (steps, cfg, samplers, schedulers).
        
        Note: Contract constraints getter not yet implemented.
        Returns None - validation will be permissive.
        """
        # TODO: Add getModelConstraints to contract when needed
        return None

    def get_all_model_hashes(self) -> List[bytes]:
        """Get all model hashes from chain as raw bytes."""
        if not self.enabled or not self._contract:
            return []

        try:
            return self._contract.functions.getAllModelHashes().call()
        except Exception as e:
            logger.error(f"Error fetching model hashes: {e}")
            return []

    def get_all_active_models(self) -> List[str]:
        """Get all active model hashes from chain as hex strings."""
        hashes = self.get_all_model_hashes()
        return [h.hex() for h in hashes]

    def get_total_models(self) -> int:
        """Get total number of registered models."""
        if not self.enabled or not self._contract:
            return 0
        
        try:
            return self._contract.functions.totalModels().call()
        except Exception as e:
            logger.error(f"Error fetching total models: {e}")
            return 0

    def fetch_all_models(self, force_refresh: bool = False) -> Dict[str, OnChainModelInfo]:
        """
        Fetch all registered models from the blockchain.
        
        This is the primary method for getting the complete model registry.
        Results are cached and can be force-refreshed.
        
        Falls back to local catalog if blockchain fetching fails.
        
        Returns:
            Dict mapping display_name -> OnChainModelInfo
        """
        if self._cache_initialized and not force_refresh:
            return self._model_cache
        
        self._model_cache = {}
        temp_models = []
        blockchain_success = False
        
        # Try blockchain first
        if self.enabled and self._contract:
            try:
                # Fetch all model hashes, then get each model's details
                model_hashes = self.get_all_model_hashes()
                logger.info(f"Fetching {len(model_hashes)} models from blockchain...")
                
                for model_hash in model_hashes:
                    try:
                        model_info = self.get_model_by_hash(model_hash)
                        if model_info:
                            temp_models.append(model_info)
                            blockchain_success = True
                    except Exception as e:
                        logger.warning(f"Failed to fetch model {model_hash.hex()}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error fetching models from chain: {e}")
        
        # Fall back to local catalog if blockchain failed or returned no models
        if not blockchain_success or not temp_models:
            logger.info("Falling back to local catalog for model data...")
            temp_models = self._load_models_from_catalog()
        
        # Process models
        seen_names = set()
        for model_info in temp_models:
            name_lower = model_info.display_name.lower()
            
            # Avoid duplicates
            if model_info.display_name in seen_names:
                continue
            seen_names.add(model_info.display_name)
            
            # Load download URLs from fallback if not available from chain
            if not model_info.files:
                model_info.files = self._load_fallback_download_urls(model_info.display_name)
            
            # Index by display_name for easy lookup
            self._model_cache[model_info.display_name] = model_info
            # Also index by common variants
            if model_info.file_name:
                self._model_cache[model_info.file_name] = model_info
                self._model_cache[model_info.get_model_id()] = model_info
        
        self._cache_initialized = True
        logger.info(f"Loaded {len(seen_names)} unique models")
        return self._model_cache
    
    def _load_models_from_catalog(self) -> List[OnChainModelInfo]:
        """Load models from local catalog files as fallback."""
        import json
        import os
        
        models = []
        
        # Try multiple possible paths for the model reference repository
        ref_path = os.environ.get("GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH", "")
        
        # Build list of possible catalog paths
        catalog_paths = []
        
        if ref_path:
            catalog_paths.append(os.path.join(ref_path, "stable_diffusion.json"))
        
        # Docker paths
        catalog_paths.extend([
            "/app/grid-image-model-reference/stable_diffusion.json",
            "/app/comfy-bridge/model_configs.json",
        ])
        
        # Auto-detect relative to this file's location (for local development)
        this_dir = os.path.dirname(os.path.abspath(__file__))
        comfy_bridge_root = os.path.dirname(this_dir)
        dev_root = os.path.dirname(comfy_bridge_root)
        
        catalog_paths.extend([
            os.path.join(dev_root, "grid-image-model-reference", "stable_diffusion.json"),
            os.path.join(comfy_bridge_root, "model_configs.json"),
        ])
        
        for catalog_path in catalog_paths:
            try:
                if not os.path.exists(catalog_path):
                    continue
                    
                with open(catalog_path, 'r') as f:
                    catalog = json.load(f)
                
                logger.info(f"Loading models from {catalog_path}...")
                
                for name, data in catalog.items():
                    # Determine model type
                    model_type = ModelType.IMAGE_MODEL
                    name_lower = name.lower()
                    if 'video' in name_lower or 'wan' in name_lower or 'ltx' in name_lower:
                        model_type = ModelType.VIDEO_MODEL
                    elif 'llm' in name_lower or 'text' in name_lower:
                        model_type = ModelType.TEXT_MODEL
                    
                    # Get file info from config.files or top-level files
                    config = data.get("config", {})
                    files_data = config.get("files", []) or data.get("files", [])
                    download_info = config.get("download", [])
                    
                    # Get config-level download URL as fallback
                    config_download_url = (
                        config.get("download_url") or 
                        config.get("file_url") or 
                        data.get("download_url") or
                        data.get("url") or
                        ""
                    )
                    
                    # Build maps of file_name -> download_url and file_name -> type from download array
                    download_urls = {}
                    download_types = {}
                    for dl in download_info:
                        if isinstance(dl, dict):
                            fn = dl.get("file_name", "")
                            url = dl.get("file_url") or dl.get("download_url") or dl.get("url", "")
                            file_type = dl.get("type", "")
                            if fn:
                                if url:
                                    download_urls[fn] = url
                                if file_type:
                                    download_types[fn] = file_type
                    
                    files = []
                    for file_info in files_data:
                        if isinstance(file_info, dict):
                            file_path = file_info.get("path", "")
                            # Get URL from file_info first, then fall back to download_urls map, then config-level URL
                            url = (
                                file_info.get("url") or 
                                file_info.get("file_url") or 
                                file_info.get("download_url") or
                                download_urls.get(file_path, "") or
                                config_download_url
                            )
                            # Get type from file_info first, then from download_types map, then infer from URL/filename
                            file_type = (
                                file_info.get("type") or 
                                download_types.get(file_path, "") or
                                self._infer_file_type_from_url(url) or
                                self._infer_file_type_from_filename(file_path) or
                                "checkpoint"
                            )
                            
                            files.append(ModelFile(
                                file_name=file_path,
                                file_type=file_type,
                                download_url=url,
                                mirror_url=file_info.get("mirror_url", ""),
                                sha256_hash=file_info.get("sha256") or file_info.get("sha256sum", ""),
                                size_bytes=int(file_info.get("size_bytes", 0) or 0),
                            ))
                    
                    # Get size
                    size_bytes = int((data.get("size_mb") or data.get("size_gb", 0) * 1024 or 0) * 1024 * 1024)
                    
                    model_info = OnChainModelInfo(
                        model_hash="",
                        model_type=model_type,
                        file_name=data.get("filename", name),
                        display_name=data.get("name") or data.get("display_name") or name,
                        description=data.get("description", f"{name} model"),
                        is_nsfw=data.get("nsfw", False),
                        size_bytes=size_bytes,
                        inpainting=data.get("inpainting", False),
                        img2img=data.get("img2img", False),
                        controlnet=data.get("controlnet", False),
                        lora=data.get("type") == "loras",
                        base_model=data.get("baseline") or data.get("base_model", ""),
                        architecture=data.get("style") or data.get("type", "checkpoint"),
                        is_active=True,
                        files=files,
                    )
                    models.append(model_info)
                
                if models:
                    logger.info(f"Loaded {len(models)} models from catalog")
                    return models
                    
            except Exception as e:
                logger.debug(f"Could not load catalog {catalog_path}: {e}")
                continue
        
        return models

    def get_registered_model_names(self) -> List[str]:
        """
        Get list of all registered model display names from blockchain.
        
        This is the primary function for model discovery.
        """
        models = self.fetch_all_models()
        # Return unique display names only
        seen = set()
        names = []
        for model in models.values():
            if model.display_name not in seen:
                seen.add(model.display_name)
                names.append(model.display_name)
        return names

    def get_models_by_type(self, model_type: ModelType) -> List[OnChainModelInfo]:
        """Get all models of a specific type."""
        models = self.fetch_all_models()
        return [m for m in models.values() if m.model_type == model_type]

    def find_model(self, name: str) -> Optional[OnChainModelInfo]:
        """
        Find a model by name (case-insensitive, supports partial matching and aliases).
        
        Searches display_name, file_name, and model_id.
        Also checks MODEL_NAME_ALIASES for user-friendly name mappings.
        """
        models = self.fetch_all_models()
        
        # Exact match first
        if name in models:
            return models[name]
        
        # Check aliases (case-insensitive)
        name_lower = name.lower()
        alias_target = MODEL_NAME_ALIASES.get(name_lower)
        if alias_target:
            if alias_target in models:
                return models[alias_target]
            # Also try case-insensitive match on alias target
            for key, model in models.items():
                if key.lower() == alias_target.lower():
                    return model
        
        # Case-insensitive match
        for key, model in models.items():
            if key.lower() == name_lower:
                return model
        
        # Normalized match (replace dots/hyphens with underscores)
        normalized = name_lower.replace(".", "_").replace("-", "_")
        for key, model in models.items():
            key_normalized = key.lower().replace(".", "_").replace("-", "_")
            if key_normalized == normalized:
                return model
        
        # Partial match on display_name
        for model in models.values():
            if name_lower in model.display_name.lower():
                return model
        
        return None

    def validate_params(
        self,
        file_name: str,
        steps: int,
        cfg: float,
        sampler: Optional[str] = None,
        scheduler: Optional[str] = None,
    ) -> ValidationResult:
        """Validate job parameters against on-chain constraints."""
        if not self.enabled:
            return ValidationResult(is_valid=True)

        if not self.is_model_registered(file_name):
            return ValidationResult(
                is_valid=False,
                reason=f"Model '{file_name}' not registered on-chain",
            )

        model_id = file_name.replace(".safetensors", "").replace(".ckpt", "").replace(".pt", "")
        constraints = self.get_constraints(model_id)

        if not constraints:
            return ValidationResult(is_valid=True)

        if constraints.steps_max > 0:
            if steps < constraints.steps_min:
                return ValidationResult(
                    is_valid=False,
                    reason=f"steps {steps} below min {constraints.steps_min}",
                )
            if steps > constraints.steps_max:
                return ValidationResult(
                    is_valid=False,
                    reason=f"steps {steps} exceeds max {constraints.steps_max}",
                )

        if constraints.cfg_max > 0:
            if cfg < constraints.cfg_min:
                return ValidationResult(
                    is_valid=False,
                    reason=f"cfg {cfg} below min {constraints.cfg_min}",
                )
            if cfg > constraints.cfg_max:
                return ValidationResult(
                    is_valid=False,
                    reason=f"cfg {cfg} exceeds max {constraints.cfg_max}",
                )

        if sampler and constraints.allowed_samplers:
            if sampler not in constraints.allowed_samplers:
                return ValidationResult(
                    is_valid=False,
                    reason=f"sampler '{sampler}' not allowed",
                )

        if scheduler and constraints.allowed_schedulers:
            if scheduler not in constraints.allowed_schedulers:
                return ValidationResult(
                    is_valid=False,
                    reason=f"scheduler '{scheduler}' not allowed",
                )

        return ValidationResult(is_valid=True)

    def refresh_cache(self) -> None:
        """Force refresh the model cache from blockchain."""
        self._cache_initialized = False
        self.fetch_all_models(force_refresh=True)


_client_instance: Optional[ModelVaultClient] = None


def get_modelvault_client(enabled: bool = True) -> ModelVaultClient:
    """Get singleton ModelVault client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ModelVaultClient(enabled=enabled)
    return _client_instance


def get_chain_registered_models() -> List[str]:
    """
    Get all model names registered on the blockchain.
    
    This is the primary function for model discovery.
    """
    client = get_modelvault_client()
    return client.get_registered_model_names()


def get_model_download_info(model_name: str) -> Optional[OnChainModelInfo]:
    """
    Get complete model info including download URLs from blockchain.
    
    Returns None if model not found.
    """
    client = get_modelvault_client()
    return client.find_model(model_name)
