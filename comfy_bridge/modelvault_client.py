"""
ModelVault Client - On-chain model validation for the comfy-bridge.
Queries the ModelVault contract on Base Sepolia to validate models.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)

import os

MODELVAULT_CONTRACT_ADDRESS = os.getenv("MODELVAULT_CONTRACT", "0xe660455D4A83bbbbcfDCF4219ad82447a831c8A1")
MODELVAULT_RPC_URL = os.getenv("MODELVAULT_RPC_URL", "https://sepolia.base.org")
MODELVAULT_CHAIN_ID = 84532


class ModelType(IntEnum):
    SD15 = 0
    SDXL = 1
    VIDEO = 2
    FLUX = 3
    OTHER = 4


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


@dataclass
class ValidationResult:
    is_valid: bool
    reason: Optional[str] = None


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
        "name": "getModel",
        "outputs": [
            {
                "components": [
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "modelType", "type": "uint8"},
                    {"name": "fileName", "type": "string"},
                    {"name": "displayName", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "isNSFW", "type": "bool"},
                    {"name": "sizeBytes", "type": "uint256"},
                    {"name": "inpainting", "type": "bool"},
                    {"name": "img2img", "type": "bool"},
                    {"name": "controlnet", "type": "bool"},
                    {"name": "lora", "type": "bool"},
                    {"name": "baseModel", "type": "string"},
                    {"name": "architecture", "type": "string"},
                    {"name": "isActive", "type": "bool"},
                ],
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "modelId", "type": "string"}],
        "name": "getModelConstraints",
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
                ],
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getAllActiveModels",
        "outputs": [{"type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ModelVaultClient:
    """Client for querying the ModelVault contract on Base Sepolia."""

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
        except ImportError:
            logger.warning("web3 package not installed. ModelVault validation disabled. Install with: pip install web3")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize ModelVault client: {e}")
            self.enabled = False

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
        """Get model info from chain."""
        if not self.enabled or not self._contract:
            return None

        try:
            model_hash = self.hash_model(file_name)
            result = self._contract.functions.getModel(model_hash).call()

            return OnChainModelInfo(
                model_hash=result[0].hex(),
                model_type=ModelType(result[1]),
                file_name=result[2],
                display_name=result[3],
                description=result[4],
                is_nsfw=result[5],
                size_bytes=result[6],
                inpainting=result[7],
                img2img=result[8],
                controlnet=result[9],
                lora=result[10],
                base_model=result[11],
                architecture=result[12],
                is_active=result[13],
            )
        except Exception as e:
            logger.debug(f"Model not found on chain: {file_name} ({e})")
            return None

    def get_constraints(self, model_id: str) -> Optional[ModelConstraints]:
        """Get model constraints (steps, cfg, samplers, schedulers)."""
        if not self.enabled or not self._contract:
            return None

        try:
            result = self._contract.functions.getModelConstraints(model_id).call()

            def bytes32_to_string(b: bytes) -> str:
                return b.rstrip(b"\x00").decode("utf-8", errors="ignore")

            return ModelConstraints(
                steps_min=result[0],
                steps_max=result[1],
                cfg_min=result[2] / 10.0,
                cfg_max=result[3] / 10.0,
                clip_skip=result[4],
                allowed_samplers=[bytes32_to_string(s) for s in result[5] if bytes32_to_string(s)],
                allowed_schedulers=[bytes32_to_string(s) for s in result[6] if bytes32_to_string(s)],
            )
        except Exception as e:
            logger.debug(f"No constraints found for model: {model_id} ({e})")
            return None

    def get_all_active_models(self) -> List[str]:
        """Get all active model hashes from chain."""
        if not self.enabled or not self._contract:
            return []

        try:
            result = self._contract.functions.getAllActiveModels().call()
            return [h.hex() for h in result]
        except Exception as e:
            logger.error(f"Error fetching active models: {e}")
            return []

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


_client_instance: Optional[ModelVaultClient] = None


def get_modelvault_client(enabled: bool = True) -> ModelVaultClient:
    """Get singleton ModelVault client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ModelVaultClient(enabled=enabled)
    return _client_instance
