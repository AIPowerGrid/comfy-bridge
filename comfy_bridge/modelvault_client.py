"""
ModelVault Client - On-chain model registry for the comfy-bridge.
The blockchain is the SINGLE source of truth for registered models.
Queries the ModelVault contract on Base Mainnet for model discovery, validation, and downloads.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import IntEnum
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

import os

MODELVAULT_CONTRACT_ADDRESS = os.getenv("MODELVAULT_CONTRACT", "0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609")
MODELVAULT_RPC_URL = os.getenv("MODELVAULT_RPC_URL", "https://mainnet.base.org")
MODELVAULT_CHAIN_ID = 8453

# Alternative Base Mainnet RPC endpoints for fallback
BASE_RPC_ENDPOINTS = [
    "https://mainnet.base.org",  # Primary public endpoint
    "https://base.llamarpc.com",  # Alternative public endpoint
    "https://base.blockpi.network/v1/rpc/public",  # BlockPi public endpoint
    "https://base.gateway.tenderly.co",  # Tenderly public endpoint
]

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
    # Model constraints (per-model generation limits)
    constraints: Optional[ModelConstraints] = None
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


# ABI matching Grid proxy ModelVault module deployed at 0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
# Grid ModelVault struct: modelHash, modelType, fileName, name, version, ipfsCid, downloadUrl,
#                        sizeBytes, quantization, format, vramMB, baseModel, inpainting, img2img,
#                        controlnet, lora, isActive, isNSFW, timestamp, creator
MODEL_REGISTRY_ABI = [
    {
        "inputs": [{"name": "modelId", "type": "uint256"}],
        "name": "isModelExists",
        "outputs": [{"type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "modelId", "type": "uint256"}],
        "name": "getModel",
        "outputs": [
            {
                "components": [
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "modelType", "type": "uint8"},
                    {"name": "fileName", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "ipfsCid", "type": "string"},
                    {"name": "downloadUrl", "type": "string"},
                    {"name": "sizeBytes", "type": "uint256"},
                    {"name": "quantization", "type": "string"},
                    {"name": "format", "type": "string"},
                    {"name": "vramMB", "type": "uint32"},
                    {"name": "baseModel", "type": "string"},
                    {"name": "inpainting", "type": "bool"},
                    {"name": "img2img", "type": "bool"},
                    {"name": "controlnet", "type": "bool"},
                    {"name": "lora", "type": "bool"},
                    {"name": "isActive", "type": "bool"},
                    {"name": "isNSFW", "type": "bool"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "creator", "type": "address"},
                ],
                "type": "tuple",
            },
        ],
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
                    {"name": "version", "type": "string"},
                    {"name": "ipfsCid", "type": "string"},
                    {"name": "downloadUrl", "type": "string"},
                    {"name": "sizeBytes", "type": "uint256"},
                    {"name": "quantization", "type": "string"},
                    {"name": "format", "type": "string"},
                    {"name": "vramMB", "type": "uint32"},
                    {"name": "baseModel", "type": "string"},
                    {"name": "inpainting", "type": "bool"},
                    {"name": "img2img", "type": "bool"},
                    {"name": "controlnet", "type": "bool"},
                    {"name": "lora", "type": "bool"},
                    {"name": "isActive", "type": "bool"},
                    {"name": "isNSFW", "type": "bool"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "creator", "type": "address"},
                ],
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getModelCount",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "modelHash", "type": "bytes32"}],
        "name": "getConstraints",
        "outputs": [
            {
                "components": [
                    {"name": "stepsMin", "type": "uint16"},
                    {"name": "stepsMax", "type": "uint16"},
                    {"name": "cfgMinTenths", "type": "uint16"},
                    {"name": "cfgMaxTenths", "type": "uint16"},
                    {"name": "clipSkip", "type": "uint8"},
                    {"name": "allowedSamplers", "type": "bytes32[]"},
                    {"name": "allowedSchedulers", "type": "bytes32[]"},
                    {"name": "exists", "type": "bool"},
                ],
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


class ModelVaultClient:
    """
    Client for querying the ModelVault contract on Base Mainnet.
    
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
        self.rpc_endpoints = BASE_RPC_ENDPOINTS.copy()  # List of endpoints to try
        self.current_rpc_index = 0  # Track which endpoint we're using
        self._web3 = None
        self._contract = None
        # Cache for model data (refreshed on demand)
        self._model_cache: Dict[str, OnChainModelInfo] = {}
        self._cache_initialized = False
        self._is_v2_contract = False  # Detect if contract has V2 features

        if enabled:
            self._init_web3_with_fallback()

    def _call_with_timeout(self, func, timeout=35):
        """
        Execute a function with a hard timeout using ThreadPoolExecutor.
        This ensures contract calls don't hang indefinitely even if HTTPProvider timeout fails.
        
        Args:
            func: The function to call
            timeout: Maximum time to wait in seconds (default 35s, slightly longer than HTTPProvider timeout)
        
        Returns:
            The result of the function call
        
        Raises:
            TimeoutError: If the call exceeds the timeout
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError(f"Contract call timed out after {timeout} seconds")
    
    def _retry_with_backoff(self, func, max_retries=3, initial_wait=1.0):
        """
        Retry a function with exponential backoff for rate limiting errors.
        Can also switch to a different RPC endpoint if persistently rate limited.
        Handles timeouts and connection errors gracefully.
        
        Args:
            func: The function to call
            max_retries: Maximum number of retries
            initial_wait: Initial wait time in seconds
        
        Returns:
            The result of the function call
        """
        wait_time = initial_wait
        last_error = None
        consecutive_429s = 0
        consecutive_timeouts = 0
        rpc_switches_this_call = 0
        max_rpc_switches = len(self.rpc_endpoints) * 2  # Prevent infinite loops
        
        for attempt in range(max_retries + 1):
            try:
                # Wrap function call with hard timeout to prevent indefinite hangs
                result = self._call_with_timeout(func, timeout=35)
                consecutive_429s = 0  # Reset on success
                consecutive_timeouts = 0  # Reset on success
                return result
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                last_error = e
                
                # Check for timeout errors
                is_timeout = (
                    "timeout" in error_msg.lower() or 
                    "timed out" in error_msg.lower() or
                    "Timeout" in error_type or
                    "ReadTimeout" in error_type or
                    "ConnectTimeout" in error_type
                )
                
                # Check if it's a rate limiting error (429)
                is_rate_limit = "429" in error_msg or "Too Many Requests" in error_msg
                
                if is_timeout:
                    consecutive_timeouts += 1
                    logger.debug(f"Timeout on attempt {attempt + 1}/{max_retries + 1}: {error_type}")
                    
                    # If we've had multiple timeouts, try switching RPC endpoint
                    if consecutive_timeouts >= 2 and len(self.rpc_endpoints) > 1 and rpc_switches_this_call < max_rpc_switches:
                        logger.debug(f"Multiple timeouts detected, switching RPC endpoint...")
                        self._switch_rpc_endpoint()
                        rpc_switches_this_call += 1
                        consecutive_timeouts = 0
                        continue
                    
                    if attempt < max_retries:
                        logger.debug(f"Timeout, waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        wait_time = min(wait_time * 2, 10)  # Cap at 10 seconds for timeouts
                        continue
                    else:
                        logger.warning(f"Max retries reached after timeout. Giving up.")
                        raise
                
                elif is_rate_limit:
                    consecutive_429s += 1
                    
                    # If we've had multiple 429s, try switching RPC endpoint
                    if consecutive_429s >= 2 and len(self.rpc_endpoints) > 1 and rpc_switches_this_call < max_rpc_switches:
                        logger.debug(f"Multiple rate limits detected, switching RPC endpoint...")
                        self._switch_rpc_endpoint()
                        rpc_switches_this_call += 1
                        consecutive_429s = 0
                        continue
                    
                    if attempt < max_retries:
                        logger.debug(f"Rate limited, waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        wait_time = min(wait_time * 2, 30)  # Cap at 30 seconds
                        continue
                    else:
                        logger.error(f"Max retries reached. RPC endpoint still rate limiting after {max_retries} attempts")
                        raise
                else:
                    # For other errors, log and raise immediately (don't retry)
                    logger.debug(f"Non-retryable error: {error_type}: {error_msg[:100]}")
                    raise
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
    
    def _switch_rpc_endpoint(self):
        """Switch to the next available RPC endpoint."""
        if not self.enabled or len(self.rpc_endpoints) <= 1:
            return
        
        old_endpoint = self.rpc_url
        self.current_rpc_index = (self.current_rpc_index + 1) % len(self.rpc_endpoints)
        new_endpoint = self.rpc_endpoints[self.current_rpc_index]
        
        logger.info(f"Switching RPC endpoint from {old_endpoint} to {new_endpoint}")
        
        try:
            from web3 import Web3
            from web3.providers import HTTPProvider
            
            provider = HTTPProvider(
                new_endpoint,
                request_kwargs={'timeout': 30}
            )
            
            self._web3 = Web3(provider)
            self._contract = self._web3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=MODEL_REGISTRY_ABI,
            )
            self.rpc_url = new_endpoint
            logger.info(f"Successfully switched to {new_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to switch to {new_endpoint}: {e}")
            # Continue with the current endpoint even if switch failed

    def _init_web3_with_fallback(self):
        """Initialize web3 connection with fallback RPC endpoints."""
        try:
            from web3 import Web3
            from web3.providers import HTTPProvider
        except ImportError:
            logger.warning("web3 package not installed. ModelVault validation disabled. Install with: pip install web3")
            self.enabled = False
            return
        
        # Try each RPC endpoint until one works
        for i, endpoint in enumerate(self.rpc_endpoints):
            try:
                logger.info(f"Attempting to connect to RPC endpoint: {endpoint}")
                
                # Configure provider with longer timeout
                provider = HTTPProvider(
                    endpoint,
                    request_kwargs={'timeout': 30}  # 30 second timeout
                )
                
                self._web3 = Web3(provider)
                
                # Test the connection
                chain_id = self._web3.eth.chain_id
                if chain_id != MODELVAULT_CHAIN_ID:
                    logger.warning(f"Wrong chain ID {chain_id} from {endpoint}, expected {MODELVAULT_CHAIN_ID}")
                    continue
                
                self._contract = self._web3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=MODEL_REGISTRY_ABI,
                )
                
                # Test contract call
                _ = self._retry_with_backoff(
                    lambda: self._contract.functions.getModelCount().call(),
                    max_retries=2,
                    initial_wait=0.5
                )
                
                self.current_rpc_index = i
                self.rpc_url = endpoint
                logger.info(f"ModelVault client initialized with {endpoint} (contract: {self.contract_address[:10]}...)")
                
                # Try to detect if this is a V2 contract
                self._detect_contract_version()
                return
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    logger.warning(f"RPC endpoint {endpoint} is rate limiting, trying next...")
                else:
                    logger.warning(f"Failed to connect to {endpoint}: {type(e).__name__}: {e}")
                continue
        
        # If all endpoints failed, disable the client
        logger.error(f"All RPC endpoints failed. ModelVault validation disabled.")
        self.enabled = False
    
    def _init_web3(self):
        """Legacy method for compatibility - calls the new fallback version."""
        self._init_web3_with_fallback()

    def _detect_contract_version(self):
        """Detect contract version. Grid proxy ModelVault is deployed at 0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609"""
        # Grid ModelVault has download URLs and additional fields
        self._is_v2_contract = True
        logger.info("Grid ModelVault contract (with on-chain download URLs)")
    
    def _load_descriptions_from_catalog(self) -> Dict[str, str]:
        """Load model descriptions from blockchain only (no JSON fallback)."""
        # Descriptions are now generated from model names or fetched from blockchain
        # No longer loading from stable_diffusion.json
        return {}
    
    def _get_description_for_model(self, display_name: str, file_name: str, descriptions_cache: Dict[str, str]) -> str:
        """Get description for a model from cache, with multiple fallback lookups."""
        # Try direct match first
        if display_name in descriptions_cache:
            return descriptions_cache[display_name]
        if display_name.lower() in descriptions_cache:
            return descriptions_cache[display_name.lower()]
        if file_name in descriptions_cache:
            return descriptions_cache[file_name]
        if file_name.lower() in descriptions_cache:
            return descriptions_cache[file_name.lower()]
        
        # Try normalized matching (handle underscores/hyphens/dots)
        name_normalized = display_name.lower().replace("-", "_").replace(".", "_")
        for key, desc in descriptions_cache.items():
            key_normalized = key.lower().replace("-", "_").replace(".", "_")
            if key_normalized == name_normalized:
                return desc
        
        # Generate a fallback description based on model name
        return self._generate_description(display_name)
    
    def _generate_description(self, display_name: str) -> str:
        """Generate a basic description based on model name patterns."""
        name_lower = display_name.lower()
        
        if "wan2.2" in name_lower or "wan2_2" in name_lower:
            if "ti2v" in name_lower or "i2v" in name_lower:
                return "WAN 2.2 Image-to-Video generation model"
            elif "t2v" in name_lower:
                if "hq" in name_lower:
                    return "WAN 2.2 Text-to-Video 14B model - High quality mode"
                return "WAN 2.2 Text-to-Video 14B model"
            return "WAN 2.2 Video generation model"
        
        if "flux" in name_lower:
            if "kontext" in name_lower:
                return "FLUX Kontext model for context-aware image generation"
            if "krea" in name_lower:
                return "FLUX Krea model - Advanced image generation"
            return "FLUX.1 model for high-quality image generation"
        
        if "sdxl" in name_lower or "xl" in name_lower:
            return "Stable Diffusion XL model"
        
        if "chroma" in name_lower:
            return "Chroma model for image generation"
        
        if "ltxv" in name_lower:
            return "LTX Video generation model"
        
        return f"{display_name} model"

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
            # Grid ModelVault: getModelByHash throws if not found, so catch and return False
            try:
                result = self._contract.functions.getModelByHash(model_hash).call()
                return result[0] != b'\x00' * 32  # Check if modelHash is not zero
            except Exception:
                return False
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
            # Grid ModelVault struct order:
            # [0] modelHash, [1] modelType, [2] fileName, [3] name (displayName), [4] version,
            # [5] ipfsCid, [6] downloadUrl, [7] sizeBytes, [8] quantization, [9] format,
            # [10] vramMB, [11] baseModel, [12] inpainting, [13] img2img, [14] controlnet,
            # [15] lora, [16] isActive, [17] isNSFW, [18] timestamp, [19] creator
            
            model_hash_bytes = result[0]
            model_type = ModelType(result[1])
            file_name = result[2] if len(result) > 2 else ""
            display_name = result[3] if len(result) > 3 else ""
            size_bytes = result[7] if len(result) > 7 else 0
            
            # Generate description from model name patterns
            # No longer using stable_diffusion.json as source
            description = self._generate_description(display_name)
            
            model_info = OnChainModelInfo(
                model_hash=model_hash_bytes.hex(),
                model_type=model_type,
                file_name=file_name,
                display_name=display_name,
                description=description,
                is_nsfw=result[17] if len(result) > 17 else False,
                size_bytes=size_bytes,
                inpainting=result[12] if len(result) > 12 else False,
                img2img=result[13] if len(result) > 13 else False,
                controlnet=result[14] if len(result) > 14 else False,
                lora=result[15] if len(result) > 15 else False,
                base_model=result[11] if len(result) > 11 else "",
                architecture=result[9] if len(result) > 9 else "",  # format field
                is_active=result[16] if len(result) > 16 else True,
            )
            
            # Fetch constraints for this model (skip for video models)
            if model_type != ModelType.VIDEO_MODEL:
                constraints = self.get_constraints(model_hash_bytes)
                if constraints:
                    model_info.constraints = constraints
            
            return model_info
        except Exception as e:
            # Log at debug level - this is expected when ABI doesn't match or model data is malformed
            # The raw bytes are not useful to display, just note the failure
            error_str = str(e)
            if "Could not decode" in error_str or "model not found" in error_str.lower():
                # Truncate the raw bytes from the error message for cleaner logs
                logger.debug(f"Could not decode model from chain (ABI mismatch or model not found)")
            else:
                logger.debug(f"Error fetching model by hash: {type(e).__name__}")
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
        """No fallback URLs - blockchain is the single source of truth."""
        # Download URLs must be registered on the blockchain
        # No longer loading from stable_diffusion.json
        return []

    def get_constraints(self, model_hash: bytes) -> Optional[ModelConstraints]:
        """Get model constraints (steps, cfg, samplers, schedulers) from blockchain."""
        if not self.enabled or not self._contract:
            return None
        
        try:
            # Use retry logic with shorter timeout for constraints (non-critical data)
            result = self._retry_with_backoff(
                lambda: self._contract.functions.getConstraints(model_hash).call(),
                max_retries=1,  # Only 1 retry for constraints (fail fast)
                initial_wait=0.5  # Short wait
            )
            # Grid ModelVault constraints struct:
            # [0] stepsMin, [1] stepsMax, [2] cfgMinTenths, [3] cfgMaxTenths,
            # [4] clipSkip, [5] allowedSamplers, [6] allowedSchedulers, [7] exists
            
            if not result[7]:  # exists field
                return None
            
            # Convert bytes32[] to strings (sampler/scheduler names)
            samplers = []
            schedulers = []
            
            for sampler_hash in result[5]:  # allowedSamplers
                try:
                    # Try to decode as UTF-8 (may not always work for bytes32)
                    sampler_str = sampler_hash.hex()
                    samplers.append(sampler_str)
                except Exception:
                    samplers.append(sampler_hash.hex())
            
            for scheduler_hash in result[6]:  # allowedSchedulers
                try:
                    scheduler_str = scheduler_hash.hex()
                    schedulers.append(scheduler_str)
                except Exception:
                    schedulers.append(scheduler_hash.hex())
            
            return ModelConstraints(
                steps_min=result[0],
                steps_max=result[1],
                cfg_min=result[2] / 10.0,  # Convert tenths to float
                cfg_max=result[3] / 10.0,
                clip_skip=result[4],
                allowed_samplers=samplers,
                allowed_schedulers=schedulers,
            )
        except Exception as e:
            logger.debug(f"Error fetching constraints for model: {type(e).__name__}")
            return None

    def get_all_model_hashes(self) -> List[bytes]:
        """Get all model hashes from chain as raw bytes."""
        if not self.enabled or not self._contract:
            return []

        try:
            # Grid ModelVault doesn't have getAllModelHashes, so we iterate through model IDs
            total = self.get_total_models()
            hashes = []
            for model_id in range(1, total + 1):
                try:
                    model = self._contract.functions.getModel(model_id).call()
                    if model and len(model) > 0 and model[0] != b'\x00' * 32:  # Check modelHash is not zero
                        hashes.append(model[0])
                except Exception:
                    continue  # Skip invalid model IDs
            return hashes
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
            # Use retry logic for rate limiting
            return self._retry_with_backoff(
                lambda: self._contract.functions.getModelCount().call(),
                max_retries=5,  # More retries for this critical call
                initial_wait=2.0  # Start with 2 second wait
            )
        except Exception as e:
            logger.error(f"Error fetching total models: {e}")
            return 0

    def fetch_all_models(self, force_refresh: bool = False) -> Dict[str, OnChainModelInfo]:
        """
        Fetch all registered models from the blockchain.
        
        This is the primary method for getting the complete model registry.
        Results are cached and can be force-refreshed.
        
        Falls back to local catalog if blockchain fetching fails.
        Enriches model data with descriptions from local catalog.
        
        Returns:
            Dict mapping display_name -> OnChainModelInfo
        """
        if self._cache_initialized and not force_refresh:
            return self._model_cache
        
        self._model_cache = {}
        temp_models = []
        blockchain_success = False
        
        # Descriptions are now generated from model names (no JSON catalog)
        
        # Model fetching disabled - using RecipeVault instead
        # Try blockchain first (disabled - RecipeVault is now the source of truth)
        if False and self.enabled and self._contract:
            try:
                # Grid ModelVault: iterate through model IDs directly
                total = self.get_total_models()
                
                failed_count = 0
                timeout_count = 0
                # Log progress every 5 models
                for model_id in range(1, total + 1):
                    try:
                        # Use retry logic for individual model fetches
                        result = self._retry_with_backoff(
                            lambda mid=model_id: self._contract.functions.getModel(mid).call(),
                            max_retries=2,  # Reduced retries to prevent long hangs
                            initial_wait=0.5  # Shorter wait for individual fetches
                        )
                        if result and len(result) > 0 and result[0] != b'\x00' * 32:
                            # Grid ModelVault struct: parse the result
                            # [0] modelHash, [1] modelType, [2] fileName, [3] name (displayName), [4] version,
                            # [5] ipfsCid, [6] downloadUrl, [7] sizeBytes, [8] quantization, [9] format,
                            # [10] vramMB, [11] baseModel, [12] inpainting, [13] img2img, [14] controlnet,
                            # [15] lora, [16] isActive, [17] isNSFW, [18] timestamp, [19] creator
                            model_hash_bytes = result[0]
                            model_type = ModelType(result[1])
                            file_name = result[2] if len(result) > 2 else ""
                            display_name = result[3] if len(result) > 3 else ""
                            size_bytes = result[7] if len(result) > 7 else 0
                            
                            # Generate description from model name patterns
                            description = self._generate_description(display_name)
                            
                            model_info = OnChainModelInfo(
                                model_hash=model_hash_bytes.hex(),
                                model_type=model_type,
                                file_name=file_name,
                                display_name=display_name,
                                description=description,
                                is_nsfw=result[17] if len(result) > 17 else False,
                                size_bytes=size_bytes,
                                inpainting=result[12] if len(result) > 12 else False,
                                img2img=result[13] if len(result) > 13 else False,
                                controlnet=result[14] if len(result) > 14 else False,
                                lora=result[15] if len(result) > 15 else False,
                                base_model=result[11] if len(result) > 11 else "",
                                architecture=result[9] if len(result) > 9 else "",  # format field
                                is_active=result[16] if len(result) > 16 else True,
                            )
                            
                            # Fetch constraints for this model (skip for video models)
                            # Wrap in try-except to ensure constraints failure doesn't block model registration
                            if model_type != ModelType.VIDEO_MODEL:
                                try:
                                    constraints = self.get_constraints(model_hash_bytes)
                                    if constraints:
                                        model_info.constraints = constraints
                                except Exception as e:
                                    # Log but don't fail - constraints are optional
                                    logger.debug(f"Could not fetch constraints for model {model_id}: {type(e).__name__}")
                                    # Continue without constraints
                            
                            temp_models.append(model_info)
                            blockchain_success = True
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        error_type = type(e).__name__
                        # Track timeouts separately for debugging
                        if "timeout" in str(e).lower() or "Timeout" in error_type:
                            timeout_count += 1
                            logger.warning(f"Timeout fetching model {model_id}/{total}: {error_type}")
                        else:
                            logger.debug(f"Failed to fetch model {model_id}/{total}: {error_type}")
                        continue
                
                # Log summary at appropriate level (disabled - RecipeVault is now source of truth)
                if blockchain_success and temp_models:
                    pass  # Logging disabled - RecipeVault is now source of truth
                if failed_count > 0:
                    pass  # Logging disabled
            except Exception as e:
                pass  # Logging disabled - RecipeVault is now source of truth
        
        # Model fetching disabled - RecipeVault is now the source of truth
        # Return empty list since we're using RecipeVault for workflow discovery
        if not blockchain_success or not temp_models:
            temp_models = []
        
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
        """No catalog fallback - blockchain is the single source of truth."""
        # Models must be registered on the blockchain
        # No longer loading from stable_diffusion.json
        return []


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
        """Validate job parameters against on-chain constraints.
        
        If model is not registered on-chain, validation passes (no constraints to check).
        This allows processing jobs for models with valid workflows but not yet on-chain.
        Video models have no constraints applied.
        """
        if not self.enabled:
            return ValidationResult(is_valid=True)

        if not self.is_model_registered(file_name):
            # Model not on-chain - can't validate constraints, but don't reject
            # Jobs should proceed if we have a valid workflow for the model
            logger.debug(f"Model '{file_name}' not registered on-chain, skipping constraint validation")
            return ValidationResult(is_valid=True)

        # Get model info to check if it's a video model
        model_info = self.get_model_by_hash(self.hash_model(file_name))
        if model_info and model_info.model_type == ModelType.VIDEO_MODEL:
            # Video models have no constraints
            return ValidationResult(is_valid=True)

        # Get model hash from filename to fetch constraints
        model_hash = self.hash_model(file_name)
        constraints = self.get_constraints(model_hash)

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

        # Validate CFG (convert to tenths for comparison)
        cfg_tenths = int(cfg * 10)
        if constraints.cfg_max > 0:
            cfg_min_tenths = int(constraints.cfg_min * 10)
            cfg_max_tenths = int(constraints.cfg_max * 10)
            if cfg_tenths < cfg_min_tenths:
                return ValidationResult(
                    is_valid=False,
                    reason=f"cfg {cfg} below min {constraints.cfg_min}",
                )
            if cfg_tenths > cfg_max_tenths:
                return ValidationResult(
                    is_valid=False,
                    reason=f"cfg {cfg} exceeds max {constraints.cfg_max}",
                )

        # Validate sampler (hash the name and compare with bytes32 hashes)
        if sampler and constraints.allowed_samplers:
            from web3 import Web3
            sampler_hash = Web3.keccak(text=sampler)
            sampler_hash_hex = sampler_hash.hex()
            # Compare with stored hex strings (they're stored as hex from bytes32)
            if sampler_hash_hex not in constraints.allowed_samplers:
                return ValidationResult(
                    is_valid=False,
                    reason=f"sampler '{sampler}' not allowed",
                )

        # Validate scheduler (hash the name and compare with bytes32 hashes)
        if scheduler and constraints.allowed_schedulers:
            from web3 import Web3
            scheduler_hash = Web3.keccak(text=scheduler)
            scheduler_hash_hex = scheduler_hash.hex()
            # Compare with stored hex strings (they're stored as hex from bytes32)
            if scheduler_hash_hex not in constraints.allowed_schedulers:
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
