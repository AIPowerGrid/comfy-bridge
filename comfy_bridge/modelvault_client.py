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
        
        Returns:
            Dict mapping display_name -> OnChainModelInfo
        """
        if self._cache_initialized and not force_refresh:
            return self._model_cache
        
        if not self.enabled or not self._contract:
            logger.warning("ModelVault not enabled, returning empty model registry")
            return {}
        
        try:
            self._model_cache = {}
            temp_models = []
            
            # Fetch all model hashes, then get each model's details
            model_hashes = self.get_all_model_hashes()
            logger.info(f"Fetching {len(model_hashes)} models from blockchain...")
            
            for model_hash in model_hashes:
                try:
                    model_info = self.get_model_by_hash(model_hash)
                    if model_info:
                        temp_models.append(model_info)
                except Exception as e:
                    logger.warning(f"Failed to fetch model {model_hash.hex()}: {e}")
                    continue
            
            # Filter out duplicate WAN models (prefer underscore versions)
            seen_names = set()
            for model_info in temp_models:
                name_lower = model_info.display_name.lower()
                # Skip WAN models with dots in the name (prefer underscore versions)
                if 'wan2.2' in name_lower:
                    logger.debug(f"Filtering out duplicate WAN model: {model_info.display_name}")
                    continue
                
                # Avoid duplicates
                if model_info.display_name in seen_names:
                    continue
                seen_names.add(model_info.display_name)
                
                # Index by display_name for easy lookup
                self._model_cache[model_info.display_name] = model_info
                # Also index by common variants
                if model_info.file_name:
                    self._model_cache[model_info.file_name] = model_info
                    self._model_cache[model_info.get_model_id()] = model_info
            
            self._cache_initialized = True
            logger.info(f"Loaded {len(seen_names)} unique models from blockchain")
            return self._model_cache
            
        except Exception as e:
            logger.error(f"Error fetching all models from chain: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

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
        Find a model by name (case-insensitive, supports partial matching).
        
        Searches display_name, file_name, and model_id.
        """
        models = self.fetch_all_models()
        
        # Exact match first
        if name in models:
            return models[name]
        
        # Case-insensitive match
        name_lower = name.lower()
        for key, model in models.items():
            if key.lower() == name_lower:
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
