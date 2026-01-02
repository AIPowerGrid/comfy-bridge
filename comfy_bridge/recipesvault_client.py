"""
RecipesVault Client - On-chain workflow/recipe registry for the comfy-bridge.
The blockchain is the SINGLE source of truth for registered workflows/recipes.
Queries the RecipesVault contract (part of diamond proxy) on Base Mainnet for workflow discovery.
"""

import logging
import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

import os

RECIPESVAULT_CONTRACT_ADDRESS = os.getenv("RECIPESVAULT_CONTRACT", "")
RECIPESVAULT_RPC_URL = os.getenv("RECIPESVAULT_RPC_URL", os.getenv("MODELVAULT_RPC_URL", "https://mainnet.base.org"))
RECIPESVAULT_CHAIN_ID = int(os.getenv("RECIPESVAULT_CHAIN_ID", "8453"))

# Alternative Base Mainnet RPC endpoints for fallback
BASE_RPC_ENDPOINTS = [
    "https://mainnet.base.org",  # Primary public endpoint
    "https://base.llamarpc.com",  # Alternative public endpoint
    "https://base.blockpi.network/v1/rpc/public",  # BlockPi public endpoint
    "https://base.gateway.tenderly.co",  # Tenderly public endpoint
]

# ABI for RecipesVault module in diamond proxy
# This should match the RecipesVault facet interface
RECIPESVAULT_ABI = [
    {
        "inputs": [{"name": "recipeId", "type": "uint256"}],
        "name": "getRecipe",
        "outputs": [
            {
                "components": [
                    {"name": "recipeHash", "type": "bytes32"},
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "recipeName", "type": "string"},
                    {"name": "workflowJson", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "isActive", "type": "bool"},
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
        "inputs": [{"name": "recipeHash", "type": "bytes32"}],
        "name": "getRecipeByHash",
        "outputs": [
            {
                "components": [
                    {"name": "recipeHash", "type": "bytes32"},
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "recipeName", "type": "string"},
                    {"name": "workflowJson", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "isActive", "type": "bool"},
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
        "name": "getRecipesByModel",
        "outputs": [
            {
                "components": [
                    {"name": "recipeHash", "type": "bytes32"},
                    {"name": "modelHash", "type": "bytes32"},
                    {"name": "recipeName", "type": "string"},
                    {"name": "workflowJson", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "isActive", "type": "bool"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "creator", "type": "address"},
                ],
                "type": "tuple[]",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getRecipeCount",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "recipeId", "type": "uint256"}],
        "name": "isRecipeExists",
        "outputs": [{"type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass
class OnChainRecipeInfo:
    """Complete recipe/workflow information from the blockchain."""
    recipe_hash: str
    model_hash: str
    recipe_name: str
    workflow_json: str
    version: str
    is_active: bool
    timestamp: int
    creator: str
    
    def get_workflow_dict(self) -> Dict[str, Any]:
        """Parse workflow JSON string into dictionary."""
        try:
            return json.loads(self.workflow_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse workflow JSON for recipe {self.recipe_name}: {e}")
            return {}


class RecipesVaultClient:
    """
    Client for querying the RecipesVault contract (diamond proxy facet) on Base Mainnet.
    
    The blockchain is the single source of truth for workflow/recipe registration.
    All workflow discovery flows through this client.
    """

    def __init__(
        self,
        rpc_url: str = RECIPESVAULT_RPC_URL,
        contract_address: str = RECIPESVAULT_CONTRACT_ADDRESS,
        enabled: bool = True,
    ):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.enabled = enabled and bool(contract_address)
        self.rpc_endpoints = BASE_RPC_ENDPOINTS.copy()
        self.current_rpc_index = 0
        self._web3 = None
        self._contract = None
        # Cache for recipe data
        self._recipe_cache: Dict[str, OnChainRecipeInfo] = {}
        self._cache_initialized = False

        if self.enabled:
            self._init_web3_with_fallback()

    def _retry_with_backoff(self, func, max_retries=3, initial_wait=1.0):
        """Retry a function with exponential backoff for rate limiting errors."""
        wait_time = initial_wait
        last_error = None
        consecutive_429s = 0
        
        for attempt in range(max_retries + 1):
            try:
                result = func()
                consecutive_429s = 0
                return result
            except Exception as e:
                error_msg = str(e)
                last_error = e
                
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    consecutive_429s += 1
                    
                    if consecutive_429s >= 2 and len(self.rpc_endpoints) > 1:
                        self._switch_rpc_endpoint()
                        consecutive_429s = 0
                        continue
                    
                    if attempt < max_retries:
                        logger.debug(f"Rate limited, waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        wait_time = min(wait_time * 2, 30)
                        continue
                    else:
                        logger.error(f"Max retries reached. RPC endpoint still rate limiting after {max_retries} attempts")
                        raise
                else:
                    raise
        
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
                abi=RECIPESVAULT_ABI,
            )
            self.rpc_url = new_endpoint
            logger.info(f"Successfully switched to {new_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to switch to {new_endpoint}: {e}")

    def _init_web3_with_fallback(self):
        """Initialize web3 connection with fallback RPC endpoints."""
        if not self.contract_address:
            logger.warning("RecipesVault contract address not configured. RecipesVault disabled.")
            self.enabled = False
            return
            
        try:
            from web3 import Web3
            from web3.providers import HTTPProvider
        except ImportError:
            logger.warning("web3 package not installed. RecipesVault validation disabled. Install with: pip install web3")
            self.enabled = False
            return
        
        # Try each RPC endpoint until one works
        for i, endpoint in enumerate(self.rpc_endpoints):
            try:
                logger.info(f"Attempting to connect to RecipesVault RPC endpoint: {endpoint}")
                
                provider = HTTPProvider(
                    endpoint,
                    request_kwargs={'timeout': 30}
                )
                
                self._web3 = Web3(provider)
                
                # Test the connection
                chain_id = self._web3.eth.chain_id
                if chain_id != RECIPESVAULT_CHAIN_ID:
                    logger.warning(f"Wrong chain ID {chain_id} from {endpoint}, expected {RECIPESVAULT_CHAIN_ID}")
                    continue
                
                self._contract = self._web3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=RECIPESVAULT_ABI,
                )
                
                # Test contract call
                _ = self._retry_with_backoff(
                    lambda: self._contract.functions.getRecipeCount().call(),
                    max_retries=2,
                    initial_wait=0.5
                )
                
                self.current_rpc_index = i
                self.rpc_url = endpoint
                logger.info(f"RecipesVault client initialized with {endpoint} (contract: {self.contract_address[:10]}...)")
                return
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    logger.warning(f"RPC endpoint {endpoint} is rate limiting, trying next...")
                else:
                    logger.warning(f"Failed to connect to {endpoint}: {type(e).__name__}: {e}")
                continue
        
        logger.error(f"All RPC endpoints failed. RecipesVault validation disabled.")
        self.enabled = False

    @staticmethod
    def hash_recipe(recipe_name: str) -> bytes:
        """Generate recipe hash from name (keccak256)."""
        from web3 import Web3
        return Web3.keccak(text=recipe_name)

    def get_recipe(self, recipe_name: str) -> Optional[OnChainRecipeInfo]:
        """Get recipe info from chain by name."""
        if not self.enabled or not self._contract:
            return None

        try:
            recipe_hash = self.hash_recipe(recipe_name)
            return self.get_recipe_by_hash(recipe_hash)
        except Exception as e:
            logger.debug(f"Recipe not found on chain: {recipe_name} ({e})")
            return None

    def get_recipe_by_hash(self, recipe_hash: bytes) -> Optional[OnChainRecipeInfo]:
        """Get recipe info from chain by hash directly."""
        if not self.enabled or not self._contract:
            return None

        try:
            result = self._contract.functions.getRecipeByHash(recipe_hash).call()
            
            recipe_info = OnChainRecipeInfo(
                recipe_hash=result[0].hex() if isinstance(result[0], bytes) else result[0],
                model_hash=result[1].hex() if isinstance(result[1], bytes) else result[1],
                recipe_name=result[2],
                workflow_json=result[3],
                version=result[4] if len(result) > 4 else "",
                is_active=result[5] if len(result) > 5 else True,
                timestamp=result[6] if len(result) > 6 else 0,
                creator=result[7] if len(result) > 7 else "",
            )
            
            return recipe_info
        except Exception as e:
            logger.debug(f"Error fetching recipe by hash: {type(e).__name__}")
            return None

    def get_recipes_by_model(self, model_hash: bytes) -> List[OnChainRecipeInfo]:
        """Get all recipes for a specific model."""
        if not self.enabled or not self._contract:
            return []

        try:
            results = self._contract.functions.getRecipesByModel(model_hash).call()
            recipes = []
            
            for result in results:
                recipe_info = OnChainRecipeInfo(
                    recipe_hash=result[0].hex() if isinstance(result[0], bytes) else result[0],
                    model_hash=result[1].hex() if isinstance(result[1], bytes) else result[1],
                    recipe_name=result[2],
                    workflow_json=result[3],
                    version=result[4] if len(result) > 4 else "",
                    is_active=result[5] if len(result) > 5 else True,
                    timestamp=result[6] if len(result) > 6 else 0,
                    creator=result[7] if len(result) > 7 else "",
                )
                recipes.append(recipe_info)
            
            return recipes
        except Exception as e:
            logger.debug(f"Error fetching recipes by model: {type(e).__name__}")
            return []

    def get_total_recipes(self) -> int:
        """Get total number of registered recipes."""
        if not self.enabled or not self._contract:
            return 0
        
        try:
            return self._retry_with_backoff(
                lambda: self._contract.functions.getRecipeCount().call(),
                max_retries=5,
                initial_wait=2.0
            )
        except Exception as e:
            logger.error(f"Error fetching total recipes: {e}")
            return 0

    def fetch_all_recipes(self, force_refresh: bool = False) -> Dict[str, OnChainRecipeInfo]:
        """Fetch all registered recipes from the blockchain."""
        if self._cache_initialized and not force_refresh:
            return self._recipe_cache
        
        self._recipe_cache = {}
        
        if not self.enabled or not self._contract:
            logger.warning("RecipesVault not enabled or contract not available")
            return self._recipe_cache
        
        try:
            total = self.get_total_recipes()
            logger.info(f"Fetching {total} recipes from blockchain...")
            
            failed_count = 0
            for recipe_id in range(1, total + 1):
                try:
                    result = self._retry_with_backoff(
                        lambda rid=recipe_id: self._contract.functions.getRecipe(rid).call(),
                        max_retries=3,
                        initial_wait=0.5
                    )
                    
                    if result and len(result) > 0:
                        recipe_info = OnChainRecipeInfo(
                            recipe_hash=result[0].hex() if isinstance(result[0], bytes) else result[0],
                            model_hash=result[1].hex() if isinstance(result[1], bytes) else result[1],
                            recipe_name=result[2],
                            workflow_json=result[3],
                            version=result[4] if len(result) > 4 else "",
                            is_active=result[5] if len(result) > 5 else True,
                            timestamp=result[6] if len(result) > 6 else 0,
                            creator=result[7] if len(result) > 7 else "",
                        )
                        
                        # Only cache active recipes
                        if recipe_info.is_active:
                            # Index by recipe name
                            self._recipe_cache[recipe_info.recipe_name] = recipe_info
                            # Also index by normalized name
                            normalized_name = recipe_info.recipe_name.lower().replace(" ", "_").replace(".", "_")
                            self._recipe_cache[normalized_name] = recipe_info
                except Exception as e:
                    failed_count += 1
                    logger.debug(f"Failed to fetch recipe {recipe_id}: {type(e).__name__}")
                    continue
            
            if self._recipe_cache:
                logger.info(f"✓ Loaded {len(self._recipe_cache)} active recipes from blockchain")
            if failed_count > 0:
                logger.debug(f"Could not decode {failed_count}/{total} recipes")
        except Exception as e:
            logger.warning(f"Blockchain fetch failed: {type(e).__name__}: {e}")
        
        self._cache_initialized = True
        return self._recipe_cache

    def find_recipe(self, name: str) -> Optional[OnChainRecipeInfo]:
        """Find a recipe by name (case-insensitive, supports partial matching)."""
        recipes = self.fetch_all_recipes()
        
        # Exact match first
        if name in recipes:
            return recipes[name]
        
        # Case-insensitive match
        name_lower = name.lower()
        for key, recipe in recipes.items():
            if key.lower() == name_lower:
                return recipe
        
        # Normalized match
        normalized = name_lower.replace(".", "_").replace("-", "_")
        for key, recipe in recipes.items():
            key_normalized = key.lower().replace(".", "_").replace("-", "_")
            if key_normalized == normalized:
                return recipe
        
        # Partial match
        for recipe in recipes.values():
            if name_lower in recipe.recipe_name.lower():
                return recipe
        
        return None

    def refresh_cache(self) -> None:
        """Force refresh the recipe cache from blockchain."""
        self._cache_initialized = False
        self.fetch_all_recipes(force_refresh=True)


_client_instance: Optional[RecipesVaultClient] = None


def get_recipesvault_client(enabled: bool = True) -> RecipesVaultClient:
    """Get singleton RecipesVault client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = RecipesVaultClient(enabled=enabled)
    return _client_instance


def get_recipe_by_name(recipe_name: str) -> Optional[OnChainRecipeInfo]:
    """Get recipe by name from blockchain."""
    client = get_recipesvault_client()
    return client.find_recipe(recipe_name)


def get_recipe_by_model(model_hash: bytes) -> List[OnChainRecipeInfo]:
    """Get all recipes for a model from blockchain."""
    client = get_recipesvault_client()
    return client.get_recipes_by_model(model_hash)

