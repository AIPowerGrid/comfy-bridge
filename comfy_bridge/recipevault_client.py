"""
RecipeVault Client - On-chain workflow/recipe registry for the comfy-bridge.
Based on the RecipeSDK.js interface from c:/dev/recipe-sdk

When RECIPESVAULT_USE_LOCAL_SDK is enabled, reads from local files in the recipe-sdk directory.
Otherwise, queries the RecipeVault contract (part of diamond proxy) on Base Mainnet for workflow discovery.
"""

import logging
import time
import json
import gzip
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

import os

# RecipeVault uses the same diamond proxy contract as ModelVault
# Both ModelVault and RecipeVault are facets of the same diamond proxy
# If RECIPESVAULT_CONTRACT is not set, use MODELVAULT_CONTRACT (diamond proxy address)
MODELVAULT_CONTRACT = os.getenv("MODELVAULT_CONTRACT", "0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609")
RECIPESVAULT_CONTRACT_ADDRESS = os.getenv("RECIPESVAULT_CONTRACT", MODELVAULT_CONTRACT)
RECIPESVAULT_RPC_URL = os.getenv("RECIPESVAULT_RPC_URL", os.getenv("MODELVAULT_RPC_URL", "https://mainnet.base.org"))
RECIPESVAULT_CHAIN_ID = int(os.getenv("RECIPESVAULT_CHAIN_ID", "8453"))

# Local SDK mode - use files from aipg-smart-contracts directory instead of blockchain
RECIPESVAULT_USE_LOCAL_SDK = os.getenv("RECIPESVAULT_USE_LOCAL_SDK", "true").lower() == "true"
RECIPESVAULT_SDK_PATH = os.getenv("RECIPESVAULT_SDK_PATH", "aipg-smart-contracts")

# Alternative Base Mainnet RPC endpoints for fallback
BASE_RPC_ENDPOINTS = [
    "https://mainnet.base.org",  # Primary public endpoint
    "https://base.llamarpc.com",  # Alternative public endpoint
    "https://base.blockpi.network/v1/rpc/public",  # BlockPi public endpoint
    "https://base.gateway.tenderly.co",  # Tenderly public endpoint
]

# Compression enum matching the SDK
class Compression:
    NONE = 0
    GZIP = 1
    BROTLI = 2

# ABI for RecipeVault module in diamond proxy
# Matches RecipeSDK.js RECIPE_VAULT_ABI
RECIPESVAULT_ABI = [
    # Write functions (not used in read-only client)
    {
        "inputs": [
            {"name": "recipeRoot", "type": "bytes32"},
            {"name": "workflowData", "type": "bytes"},
            {"name": "canCreateNFTs", "type": "bool"},
            {"name": "isPublic", "type": "bool"},
            {"name": "compression", "type": "uint8"},
            {"name": "name", "type": "string"},
            {"name": "description", "type": "string"}
        ],
        "name": "storeRecipe",
        "outputs": [{"name": "recipeId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "recipeId", "type": "uint256"},
            {"name": "canCreateNFTs", "type": "bool"},
            {"name": "isPublic", "type": "bool"}
        ],
        "name": "updateRecipePermissions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Read functions
    {
        "inputs": [{"name": "recipeId", "type": "uint256"}],
        "name": "getRecipe",
        "outputs": [
            {
                "components": [
                    {"name": "recipeId", "type": "uint256"},
                    {"name": "recipeRoot", "type": "bytes32"},
                    {"name": "workflowData", "type": "bytes"},
                    {"name": "creator", "type": "address"},
                    {"name": "canCreateNFTs", "type": "bool"},
                    {"name": "isPublic", "type": "bool"},
                    {"name": "compression", "type": "uint8"},
                    {"name": "createdAt", "type": "uint256"},
                    {"name": "name", "type": "string"},
                    {"name": "description", "type": "string"}
                ],
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "recipeRoot", "type": "bytes32"}],
        "name": "getRecipeByRoot",
        "outputs": [
            {
                "components": [
                    {"name": "recipeId", "type": "uint256"},
                    {"name": "recipeRoot", "type": "bytes32"},
                    {"name": "workflowData", "type": "bytes"},
                    {"name": "creator", "type": "address"},
                    {"name": "canCreateNFTs", "type": "bool"},
                    {"name": "isPublic", "type": "bool"},
                    {"name": "compression", "type": "uint8"},
                    {"name": "createdAt", "type": "uint256"},
                    {"name": "name", "type": "string"},
                    {"name": "description", "type": "string"}
                ],
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "creator", "type": "address"}],
        "name": "getCreatorRecipes",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTotalRecipes",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getMaxWorkflowBytes",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "recipeId", "type": "uint256"}],
        "name": "isRecipePublic",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "recipeId", "type": "uint256"}],
        "name": "canRecipeCreateNFTs",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "recipeId", "type": "uint256"},
            {"indexed": True, "name": "recipeRoot", "type": "bytes32"},
            {"indexed": False, "name": "creator", "type": "address"}
        ],
        "name": "RecipeStored",
        "type": "event"
    }
]


@dataclass
class OnChainRecipeInfo:
    """Complete recipe/workflow information from the blockchain.
    Matches the RecipeSDK.js parseRecipe structure.
    """
    recipe_id: int
    recipe_root: str  # bytes32 hex string
    creator: str  # address
    can_create_nfts: bool
    is_public: bool
    compression: int  # Compression enum value
    created_at: int  # Unix timestamp
    name: str
    description: str
    workflow: Optional[Dict[str, Any]] = None  # Decompressed workflow JSON
    workflow_error: Optional[str] = None  # Error message if decompression failed
    
    def get_workflow_dict(self) -> Dict[str, Any]:
        """Get workflow dictionary (decompressed)."""
        if self.workflow is not None:
            return self.workflow
        return {}
    
    @property
    def recipe_name(self) -> str:
        """Alias for name to maintain backward compatibility."""
        return self.name


class RecipeVaultClient:
    """
    Client for querying the RecipeVault facet through the diamond proxy contract on Base Mainnet.
    Based on RecipeSDK.js interface from c:/dev/recipe-sdk
    
    When RECIPESVAULT_USE_LOCAL_SDK is enabled, reads from local files in the recipe-sdk directory.
    Otherwise, RecipeVault is a facet of the diamond proxy (same contract address as ModelVault).
    The diamond proxy routes function calls to the appropriate facet based on function selectors.
    
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
        # Use diamond proxy address (same as ModelVault) if not specified
        self.contract_address = contract_address or MODELVAULT_CONTRACT
        self.use_local_sdk = RECIPESVAULT_USE_LOCAL_SDK
        self.sdk_path = Path(RECIPESVAULT_SDK_PATH)
        self.enabled = enabled
        self.rpc_endpoints = BASE_RPC_ENDPOINTS.copy()
        self.current_rpc_index = 0
        self._web3 = None
        self._contract = None
        # Cache for recipe data
        self._recipe_cache: Dict[str, OnChainRecipeInfo] = {}
        self._cache_initialized = False

        if self.enabled:
            if self.use_local_sdk:
                # Resolve path - try multiple locations
                if not self.sdk_path.is_absolute():
                    # Try multiple possible locations
                    possible_paths = []
                    
                    # 1. Check /app/aipg-smart-contracts first (Docker mounted volume - highest priority)
                    if Path("/app").exists():
                        possible_paths.append(Path("/app") / "aipg-smart-contracts")
                    
                    # 2. Relative to current working directory
                    possible_paths.append(Path.cwd() / self.sdk_path)
                    
                    # 3. If we're in comfy-bridge, go up one level
                    cwd = Path.cwd()
                    if cwd.name == "comfy-bridge" or "comfy-bridge" in str(cwd):
                        possible_paths.append(cwd.parent / self.sdk_path)
                    
                    # 4. Try from /app with configured path name
                    if Path("/app").exists():
                        possible_paths.append(Path("/app") / self.sdk_path)
                        # Also try /app/comfy-bridge/../aipg-smart-contracts
                        possible_paths.append(Path("/app") / ".." / self.sdk_path)
                    
                    # 5. Try resolving as absolute from current directory
                    possible_paths.append(Path(self.sdk_path).resolve())
                    
                    # Find first existing path
                    found_path = None
                    for path in possible_paths:
                        try:
                            resolved = path.resolve()
                            if resolved.exists() and resolved.is_dir():
                                found_path = resolved
                                logger.debug(f"Found RecipeVault SDK path at: {found_path}")
                                break
                        except (OSError, ValueError):
                            continue
                    
                    if found_path:
                        self.sdk_path = found_path
                    else:
                        # Log all attempted paths for debugging
                        logger.warning(f"Recipe SDK path not found. Tried:")
                        for path in possible_paths:
                            logger.warning(f"  - {path}")
                        logger.warning(f"Using configured path: {self.sdk_path}")
                
                logger.info(f"RecipeVault using local SDK mode from aipg-smart-contracts: {self.sdk_path}")
                self._init_local_sdk()
            else:
                logger.info(f"RecipeVault using diamond proxy contract: {self.contract_address[:10]}... (same address as ModelVault)")
                self._init_web3_with_fallback()
    
    def _init_local_sdk(self):
        """Initialize local SDK mode - load recipes from recipe-sdk directory."""
        if not self.sdk_path.exists():
            logger.warning(f"Recipe SDK path does not exist: {self.sdk_path}")
            logger.warning(f"RecipeVault will be disabled. Set RECIPESVAULT_SDK_PATH to the correct path or disable with RECIPESVAULT_USE_LOCAL_SDK=false")
            logger.warning(f"Current working directory: {Path.cwd()}")
            self.enabled = False
            return
        
        logger.info(f"Loading recipes from local SDK directory: {self.sdk_path}")
        # Load recipes from JSON files in the SDK directory
        self._load_local_recipes()
    
    def _load_local_recipes(self):
        """Load recipes from JSON files in the aipg-smart-contracts directory."""
        recipe_id = 1
        
        # Search for JSON workflow files in common locations:
        # 1. Root directory
        # 2. examples/ directory
        # 3. scripts/ directory
        # 4. sdk/ directory
        search_paths = [
            self.sdk_path,  # Root
            self.sdk_path / "examples",
            self.sdk_path / "scripts",
            self.sdk_path / "sdk",
        ]
        
        found_files = set()
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            for json_file in search_path.glob("*.json"):
                # Skip non-workflow files
                if json_file.name in ["package.json", "package-lock.json", "tsconfig.json"]:
                    continue
                
                # Skip if already processed (avoid duplicates)
                if json_file in found_files:
                    continue
                
                found_files.add(json_file)
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        workflow = json.load(f)
                    
                    # Validate it's a workflow (has nodes or is a workflow structure)
                    if not isinstance(workflow, dict):
                        continue
                    
                    # Generate recipe name from filename
                    recipe_name = json_file.stem.replace("_", " ").replace("-", " ").title()
                    
                    # Calculate recipe root
                    recipe_root = self.calculate_recipe_root(workflow)
                    
                    # Create recipe info
                    recipe_info = OnChainRecipeInfo(
                        recipe_id=recipe_id,
                        recipe_root=recipe_root.hex() if isinstance(recipe_root, bytes) else recipe_root,
                        creator="0x0000000000000000000000000000000000000000",  # Local SDK - no creator
                        can_create_nfts=True,
                        is_public=True,
                        compression=Compression.NONE,
                        created_at=int(time.time()),
                        name=recipe_name,
                        description=f"Local recipe from {json_file.relative_to(self.sdk_path)}",
                        workflow=workflow,
                        workflow_error=None
                    )
                    
                    # Index by recipe name
                    self._recipe_cache[recipe_name] = recipe_info
                    # Also index by normalized name
                    normalized_name = recipe_name.lower().replace(" ", "_").replace(".", "_").replace("-", "_")
                    self._recipe_cache[normalized_name] = recipe_info
                    # Index by filename without extension
                    self._recipe_cache[json_file.stem] = recipe_info
                    
                    recipe_id += 1
                    logger.debug(f"Loaded local recipe: {recipe_name} from {json_file.relative_to(self.sdk_path)}")
                    
                except json.JSONDecodeError as e:
                    logger.debug(f"Skipping {json_file.name} - not valid JSON: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to load recipe from {json_file.name}: {e}")
                    continue
        
        self._cache_initialized = True
        unique_count = len(set(r.name for r in self._recipe_cache.values()))
        logger.info(f"Loaded {unique_count} recipes from aipg-smart-contracts")

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
        # RecipeVault uses the diamond proxy contract (same as ModelVault)
        # Both facets are accessed through the same diamond proxy address
            
        try:
            from web3 import Web3
            from web3.providers import HTTPProvider
        except ImportError:
            logger.warning("web3 package not installed. RecipeVault validation disabled. Install with: pip install web3")
            self.enabled = False
            return
        
        # Try each RPC endpoint until one works
        for i, endpoint in enumerate(self.rpc_endpoints):
            try:
                logger.info(f"Attempting to connect to RecipeVault RPC endpoint: {endpoint}")
                
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
                
                # Test contract call through diamond proxy - check if RecipeVault facet is available
                # The diamond proxy routes function calls to the appropriate facet based on function selectors
                try:
                    _ = self._retry_with_backoff(
                        lambda: self._contract.functions.getTotalRecipes().call(),
                        max_retries=2,
                        initial_wait=0.5
                    )
                    # If call succeeds, RecipeVault facet is available in the diamond
                    self.current_rpc_index = i
                    self.rpc_url = endpoint
                    logger.info(f"RecipeVault client initialized through diamond proxy at {endpoint} (contract: {self.contract_address[:10]}...)")
                    logger.info("RecipeVault facet is available in the diamond proxy")
                    return
                except Exception as test_error:
                    error_str = str(test_error)
                    # Check if it's a "function not found" error (facet not registered in diamond)
                    if "function not found" in error_str.lower() or "Grid: function not found" in error_str:
                        logger.info(f"RecipeVault facet not registered in diamond proxy at {self.contract_address[:10]}...")
                        logger.info("This is normal if RecipeVault facet is not yet registered in the diamond. Workflows will be loaded from local JSON files.")
                        self.enabled = False
                        return
                    # Re-raise other errors to try next endpoint
                    raise
                
            except Exception as e:
                error_msg = str(e)
                # Check if it's a "function not found" error (facet not registered in diamond)
                if "function not found" in error_msg.lower() or "Grid: function not found" in error_msg:
                    logger.info(f"RecipeVault facet not registered in diamond proxy at {self.contract_address[:10]}...")
                    logger.info("This is normal if RecipeVault facet is not yet registered in the diamond. Workflows will be loaded from local JSON files.")
                    self.enabled = False
                    return
                elif "429" in error_msg or "Too Many Requests" in error_msg:
                    logger.warning(f"RPC endpoint {endpoint} is rate limiting, trying next...")
                else:
                    logger.debug(f"Failed to connect to {endpoint}: {type(e).__name__}: {e}")
                continue
        
        logger.info(f"RecipeVault not available through diamond proxy - using local workflow files.")
        logger.info("This is normal if RecipeVault facet is not yet registered in the diamond proxy.")
        self.enabled = False

    def _parse_recipe(self, raw_tuple) -> OnChainRecipeInfo:
        """
        Parse raw recipe tuple from contract.
        Matches RecipeSDK.js parseRecipe method.
        """
        recipe_id = raw_tuple[0]
        recipe_root = raw_tuple[1]
        workflow_data = raw_tuple[2]  # bytes
        creator = raw_tuple[3]
        can_create_nfts = raw_tuple[4]
        is_public = raw_tuple[5]
        compression = raw_tuple[6]
        created_at = raw_tuple[7]
        name = raw_tuple[8]
        description = raw_tuple[9]
        
        # Decompress workflow data
        workflow = None
        workflow_error = None
        
        try:
            if compression == Compression.GZIP:
                # Decompress gzip data
                workflow_string = gzip.decompress(workflow_data).decode('utf-8')
            elif compression == Compression.NONE:
                # No compression, decode directly
                workflow_string = workflow_data.decode('utf-8')
            else:
                # Brotli or unknown compression - not supported yet
                workflow_error = f"Unsupported compression type: {compression}"
                logger.warning(f"Recipe {recipe_id} uses unsupported compression: {compression}")
            
            if workflow_string:
                workflow = json.loads(workflow_string)
        except Exception as e:
            workflow_error = str(e)
            logger.warning(f"Failed to decompress workflow for recipe {recipe_id}: {e}")
        
        return OnChainRecipeInfo(
            recipe_id=int(recipe_id),
            recipe_root=recipe_root.hex() if isinstance(recipe_root, bytes) else recipe_root,
            creator=creator,
            can_create_nfts=can_create_nfts,
            is_public=is_public,
            compression=int(compression),
            created_at=int(created_at),
            name=name,
            description=description,
            workflow=workflow,
            workflow_error=workflow_error
        )

    @staticmethod
    def calculate_recipe_root(workflow_json: Dict[str, Any]) -> bytes:
        """
        Calculate recipe root from workflow JSON (keccak256 of normalized JSON string).
        Matches RecipeSDK.calculateRecipeRoot()
        """
        try:
            from web3 import Web3
            json_string = json.dumps(workflow_json, sort_keys=True, separators=(',', ':'))
            return Web3.keccak(text=json_string)
        except ImportError:
            # Fallback: use sha256 if web3 not available (for local mode)
            # Note: This is not keccak256, but sufficient for local mode identification
            import hashlib
            json_string = json.dumps(workflow_json, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(json_string.encode('utf-8')).digest()

    def get_recipe(self, recipe_id: int) -> Optional[OnChainRecipeInfo]:
        """
        Get a recipe by ID with decompressed workflow.
        Matches RecipeSDK.getRecipe()
        """
        if not self.enabled:
            return None
        
        if self.use_local_sdk:
            # In local mode, find recipe by ID (1-indexed)
            recipes = list(self._recipe_cache.values())
            if 1 <= recipe_id <= len(recipes):
                # Return unique recipes (skip duplicates)
                unique_recipes = {}
                for r in recipes:
                    unique_recipes[r.recipe_id] = r
                return unique_recipes.get(recipe_id)
            return None

        if not self._contract:
            return None

        try:
            raw = self._retry_with_backoff(
                lambda: self._contract.functions.getRecipe(recipe_id).call(),
                max_retries=3,
                initial_wait=0.5
            )
            return self._parse_recipe(raw)
        except Exception as e:
            logger.debug(f"Error fetching recipe {recipe_id}: {type(e).__name__}: {e}")
            return None

    def get_recipe_by_root(self, recipe_root: bytes) -> Optional[OnChainRecipeInfo]:
        """
        Get recipe by its root hash.
        Matches RecipeSDK.getRecipeByRoot()
        """
        if not self.enabled:
            return None
        
        if self.use_local_sdk:
            # In local mode, search by recipe root
            root_hex = recipe_root.hex() if isinstance(recipe_root, bytes) else recipe_root
            for recipe in self._recipe_cache.values():
                if recipe.recipe_root == root_hex:
                    return recipe
            return None

        if not self._contract:
            return None

        try:
            raw = self._retry_with_backoff(
                lambda: self._contract.functions.getRecipeByRoot(recipe_root).call(),
                max_retries=3,
                initial_wait=0.5
            )
            # Check if recipe exists (recipeId > 0)
            if raw[0] == 0:
                return None
            return self._parse_recipe(raw)
        except Exception as e:
            logger.debug(f"Error fetching recipe by root: {type(e).__name__}: {e}")
            return None

    def get_creator_recipes(self, creator_address: str) -> List[int]:
        """
        Get all recipe IDs by a creator.
        Matches RecipeSDK.getCreatorRecipes()
        """
        if not self.enabled or not self._contract:
            return []

        try:
            ids = self._retry_with_backoff(
                lambda: self._contract.functions.getCreatorRecipes(creator_address).call(),
                max_retries=3,
                initial_wait=0.5
            )
            return [int(id) for id in ids]
        except Exception as e:
            logger.debug(f"Error fetching creator recipes: {type(e).__name__}: {e}")
            return []

    def get_total_recipes(self) -> int:
        """
        Get total recipe count.
        Matches RecipeSDK.getTotalRecipes()
        """
        if not self.enabled:
            return 0
        
        if self.use_local_sdk:
            # Return count of unique recipes
            unique_recipes = set(r.recipe_id for r in self._recipe_cache.values())
            return len(unique_recipes)
        
        if not self._contract:
            return 0
        
        try:
            total = self._retry_with_backoff(
                lambda: self._contract.functions.getTotalRecipes().call(),
                max_retries=5,
                initial_wait=2.0
            )
            return int(total)
        except Exception as e:
            logger.error(f"Error fetching total recipes: {e}")
            return 0

    def recipe_exists(self, recipe_root: bytes) -> bool:
        """
        Check if a recipe exists by root hash.
        Matches RecipeSDK.recipeExists()
        """
        recipe = self.get_recipe_by_root(recipe_root)
        return recipe is not None and recipe.recipe_id > 0

    def fetch_all_recipes(self, force_refresh: bool = False) -> Dict[str, OnChainRecipeInfo]:
        """
        Fetch all registered recipes from the blockchain or local SDK.
        Indexes by recipe name for easy lookup.
        """
        if self._cache_initialized and not force_refresh:
            return self._recipe_cache
        
        if self.use_local_sdk:
            # Reload local recipes if force refresh
            if force_refresh:
                self._recipe_cache = {}
                self._cache_initialized = False
                self._load_local_recipes()
            return self._recipe_cache
        
        self._recipe_cache = {}
        
        if not self.enabled or not self._contract:
            logger.warning("RecipeVault not enabled or contract not available")
            return self._recipe_cache
        
        try:
            total = self.get_total_recipes()
            logger.info(f"Fetching {total} recipes from blockchain...")
            
            failed_count = 0
            for recipe_id in range(1, total + 1):
                try:
                    recipe = self.get_recipe(recipe_id)
                    if recipe and recipe.is_public:
                        # Index by recipe name
                        self._recipe_cache[recipe.name] = recipe
                        # Also index by normalized name
                        normalized_name = recipe.name.lower().replace(" ", "_").replace(".", "_").replace("-", "_")
                        self._recipe_cache[normalized_name] = recipe
                except Exception as e:
                    failed_count += 1
                    logger.debug(f"Failed to fetch recipe {recipe_id}: {type(e).__name__}")
                    continue
            
            if self._recipe_cache:
                logger.info(f"✓ Loaded {len(set(r.name for r in self._recipe_cache.values()))} active recipes from blockchain")
            if failed_count > 0:
                logger.debug(f"Could not decode {failed_count}/{total} recipes")
        except Exception as e:
            logger.warning(f"Blockchain fetch failed: {type(e).__name__}: {e}")
        
        self._cache_initialized = True
        return self._recipe_cache

    def find_recipe(self, name: str) -> Optional[OnChainRecipeInfo]:
        """
        Find a recipe by name (case-insensitive, supports partial matching).
        Maintains backward compatibility with existing code.
        """
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
            if name_lower in recipe.name.lower():
                return recipe
        
        return None

    def refresh_cache(self) -> None:
        """Force refresh the recipe cache from blockchain."""
        self._cache_initialized = False
        self.fetch_all_recipes(force_refresh=True)


_client_instance: Optional[RecipeVaultClient] = None


def get_recipevault_client(enabled: bool = True) -> RecipeVaultClient:
    """Get singleton RecipeVault client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = RecipeVaultClient(enabled=enabled)
    return _client_instance


def get_recipe_by_name(recipe_name: str) -> Optional[OnChainRecipeInfo]:
    """Get recipe by name from blockchain."""
    client = get_recipevault_client()
    return client.find_recipe(recipe_name)


def get_recipe_by_model(model_hash: bytes) -> List[OnChainRecipeInfo]:
    """
    Get all recipes for a model from blockchain.
    Note: This is a placeholder - the SDK doesn't have this method.
    We'll need to iterate through all recipes and filter by model if needed.
    """
    client = get_recipevault_client()
    # Since the SDK doesn't have getRecipesByModel, we'll return empty list
    # This can be implemented by checking workflow contents if needed
    logger.debug("get_recipe_by_model not directly supported by RecipeVault SDK - returning empty list")
    return []
