#!/usr/bin/env python3
"""
Register Recipe/Workflow to RecipeVault on Blockchain

This script registers workflows/recipes (like ltxv.json) to the RecipeVault contract
on Base Mainnet through the Grid Diamond proxy.

IMPORTANT: storeRecipe() requires RECIPE_CREATOR_ROLE
Contact admin to get the role granted to your wallet.

Usage:
    python scripts/register_recipe_to_chain.py [--workflow <workflow-file>] [--dry-run]

Environment variables:
    PRIVATE_KEY - Private key with RECIPE_CREATOR_ROLE
    RECIPESVAULT_CONTRACT - Grid Diamond contract address (optional, defaults to Grid Diamond)
    RECIPESVAULT_RPC_URL - RPC URL (optional, defaults to Base Mainnet)
"""

import os
import sys
import json
import gzip
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to load .env file if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Error: web3 and eth-account packages required")
    print("Install with: pip install web3 eth-account")
    sys.exit(1)

# Contract configuration
CONTRACT_ADDRESS = os.getenv('RECIPESVAULT_CONTRACT') or os.getenv('MODELVAULT_CONTRACT', '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609')
RPC_URL = os.getenv('RECIPESVAULT_RPC_URL') or os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')
PRIVATE_KEY = os.getenv('PRIVATE_KEY') or os.getenv('WALLET_PRIVATE_KEY')

# Compression enum
COMPRESSION_NONE = 0
COMPRESSION_GZIP = 1
COMPRESSION_BROTLI = 2

# Role hashes (keccak256 of role name) - matches JS script
RECIPE_CREATOR_ROLE = Web3.keccak(text='RECIPE_CREATOR_ROLE')
ADMIN_ROLE = Web3.keccak(text='ADMIN_ROLE')

# ABI for RecipeVault (through diamond proxy) - matches JS script
RECIPE_VAULT_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "recipeRoot", "type": "bytes32"},
            {"internalType": "bytes", "name": "workflowData", "type": "bytes"},
            {"internalType": "bool", "name": "canCreateNFTs", "type": "bool"},
            {"internalType": "bool", "name": "isPublic", "type": "bool"},
            {"internalType": "uint8", "name": "compression", "type": "uint8"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"}
        ],
        "name": "storeRecipe",
        "outputs": [{"internalType": "uint256", "name": "recipeId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "recipeRoot", "type": "bytes32"}],
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
        "inputs": [],
        "name": "getTotalRecipes",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getMaxWorkflowBytes",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "role", "type": "bytes32"},
            {"internalType": "address", "name": "account", "type": "address"}
        ],
        "name": "hasRole",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
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


def calculate_recipe_root(workflow_json: dict) -> bytes:
    """Calculate recipe root hash from workflow JSON (keccak256 of JSON string).
    
    CRITICAL: Must match JS exactly - JSON.stringify() does NOT sort keys!
    """
    # Match JS: JSON.stringify(workflowJson) - no sorting, default formatting
    json_string = json.dumps(workflow_json)
    return Web3.keccak(text=json_string)


def compress_workflow(workflow_json: dict) -> dict:
    """Compress workflow JSON using gzip and return dict with bytes, sizes, etc.
    
    CRITICAL: Must match JS exactly - JSON.stringify() does NOT sort keys!
    Returns hex string to match JS ethers.hexlify() - web3.py accepts hex strings for bytes.
    """
    # Match JS: JSON.stringify(workflowJson) - no sorting, default formatting
    json_string = json.dumps(workflow_json)
    compressed = gzip.compress(json_string.encode('utf-8'))
    # Match JS: ethers.hexlify(compressed) - returns hex string with 0x prefix
    compressed_hex = Web3.to_hex(compressed)
    original_size = len(json_string)
    compressed_size = len(compressed)
    ratio = ((1 - compressed_size / original_size) * 100) if original_size > 0 else 0
    
    return {
        'bytes': compressed_hex,  # Hex string format (matches JS ethers.hexlify)
        'originalSize': original_size,
        'compressedSize': compressed_size,
        'ratio': f"{ratio:.1f}"
    }


def format_bytes(bytes_val: int) -> str:
    """Format bytes for display."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    return f"{bytes_val / (1024 * 1024):.2f} MB"


def load_workflow_file(workflow_path: str) -> dict:
    """Load workflow JSON from file."""
    workflow_file = Path(workflow_path)
    
    # Try multiple locations if relative path
    if not workflow_file.is_absolute():
        possible_paths = [
            workflow_file,  # Current directory
            Path(__file__).parent.parent / "workflows" / workflow_file.name,  # workflows/ directory
            Path(__file__).parent.parent / workflow_file,  # Relative to comfy-bridge root
        ]
        
        for path in possible_paths:
            if path.exists():
                workflow_file = path
                break
        else:
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")
    
    with open(workflow_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='Register workflow/recipe to RecipeVault')
    parser.add_argument('--workflow', '-w', default='ltxv.json', 
                       help='Workflow file to register (default: ltxv.json)')
    parser.add_argument('--name', '-n', help='Recipe name (default: derived from filename)')
    parser.add_argument('--description', '-d', default='', help='Recipe description')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be registered without actually registering')
    args = parser.parse_args()
    
    print('\n' + '=' * 60)
    print('AIPG RecipeVault - Register Recipe to Blockchain')
    if args.dry_run:
        print('                    [DRY RUN MODE]')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print(f'Contract: {CONTRACT_ADDRESS}')
    print()
    
    if args.dry_run:
        print('[DRY RUN MODE] - No transactions will be sent\n')
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        sys.exit(1)
    
    network = w3.eth.chain_id
    print(f'[SUCCESS] Connected to blockchain (Chain ID: {network})')
    
    # Load contract
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=RECIPE_VAULT_ABI)
    
    # Check for private key (only required for actual registration)
    if not PRIVATE_KEY and not args.dry_run:
        print('\n[ERROR] PRIVATE_KEY environment variable required for registration')
        print('   Set PRIVATE_KEY in .env file or use --dry-run to preview')
        sys.exit(1)
    
    # Create signer if we have a private key
    signer_account = None
    signer_address = None
    if PRIVATE_KEY and not args.dry_run:
        try:
            signer_account = Account.from_key(PRIVATE_KEY)
            signer_address = signer_account.address
            print(f'[INFO] Signer: {signer_address}')
            
            balance = w3.eth.get_balance(signer_address)
            print(f'[INFO] Balance: {w3.from_wei(balance, "ether")} ETH')
            
            if balance == 0:
                print('[ERROR] Wallet has no ETH for gas')
                sys.exit(1)
        except Exception as e:
            print(f'[ERROR] Invalid private key: {e}')
            sys.exit(1)
    
    # Check role (if not dry run) - matches JS script
    if not args.dry_run and signer_address:
        print('\n[INFO] Checking permissions...')
        try:
            has_creator_role = contract.functions.hasRole(RECIPE_CREATOR_ROLE, signer_address).call()
            has_admin_role = contract.functions.hasRole(ADMIN_ROLE, signer_address).call()
            
            if has_creator_role:
                print('   [SUCCESS] Has RECIPE_CREATOR_ROLE')
            elif has_admin_role:
                print('   [SUCCESS] Has ADMIN_ROLE (can create recipes)')
            else:
                print('   [ERROR] Missing RECIPE_CREATOR_ROLE')
                print('\n   Your wallet does not have permission to add recipes.')
                print('   Contact the admin to grant RECIPE_CREATOR_ROLE to:')
                print(f'   {signer_address}')
                print('\n   Authorized wallets:')
                print('   - 0xA218db26ed545f3476e6c3E827b595cf2E182533 (admin)')
                print('   - 0xe2dddddf4dd22e98265bbf0e6bdc1cb3a4bb26a8')
                sys.exit(1)
        except Exception as e:
            print(f'   [WARNING] Could not check role: {e}')
            print('   Proceeding anyway...')
    
    # Check current state
    print('\n[INFO] RecipeVault State:')
    try:
        total_recipes = contract.functions.getTotalRecipes().call()
        max_bytes = contract.functions.getMaxWorkflowBytes().call()
        print(f'   Total Recipes: {total_recipes}')
        print(f'   Max Size: {format_bytes(max_bytes)}')
    except Exception as e:
        print(f'   [WARNING] Could not fetch state: {e}')
        max_bytes = 0
    
    # Load workflow file
    try:
        workflow_json = load_workflow_file(args.workflow)
        print(f'\n[SUCCESS] Loaded workflow from: {args.workflow}')
        print(f'   Nodes: {len(workflow_json)}')
    except FileNotFoundError as e:
        print(f'[ERROR] {e}')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'[ERROR] Invalid JSON in workflow file: {e}')
        sys.exit(1)
    
    # Compress workflow
    print('\n[INFO] Compressing workflow...')
    compressed = compress_workflow(workflow_json)
    print(f'   {format_bytes(compressed["originalSize"])} -> {format_bytes(compressed["compressedSize"])} ({compressed["ratio"]}% reduction)')
    
    if max_bytes > 0 and compressed["compressedSize"] > max_bytes:
        print(f'[ERROR] Workflow too large! Max: {format_bytes(max_bytes)}')
        sys.exit(1)
    
    # Calculate recipe root
    recipe_root = calculate_recipe_root(workflow_json)
    recipe_root_hex = recipe_root.hex() if isinstance(recipe_root, bytes) else recipe_root
    print(f'\n[INFO] Recipe Root: 0x{recipe_root_hex[:22]}...')
    
    # Check if recipe already exists
    print('\n[INFO] Checking if recipe exists...')
    try:
        existing = contract.functions.getRecipeByRoot(recipe_root).call()
        if existing[0] > 0:
            print(f'   [WARNING] Recipe already exists: Recipe #{existing[0]}')
            print(f'   Name: {existing[8]}')
            print(f'   Creator: {existing[3]}')
            return
    except Exception:
        pass
    print('   [SUCCESS] Recipe is new')
    
    # Determine recipe name
    recipe_name = args.name
    if not recipe_name:
        # Derive from filename
        workflow_file = Path(args.workflow)
        recipe_name = workflow_file.stem.replace('_', ' ').replace('-', ' ').title()
    
    recipe_description = args.description or f'{recipe_name} workflow for AI generation'
    
    print('\n[INFO] Recipe Details:')
    print(f'   Name: {recipe_name}')
    print(f'   Description: {recipe_description[:50]}...' if len(recipe_description) > 50 else f'   Description: {recipe_description}')
    print(f'   Can Create NFTs: true')
    print(f'   Is Public: true')
    print(f'   Compression: Gzip')
    
    if args.dry_run:
        print('\n' + '=' * 60)
        print('   [DRY RUN COMPLETE]')
        print('')
        print('   To submit, run without --dry-run:')
        print('   python scripts/register_recipe_to_chain.py --workflow ltxv.json')
        print('')
        print('   NOTE: Your wallet needs RECIPE_CREATOR_ROLE')
        print('=' * 60 + '\n')
        return
    
    # Submit transaction
    print('\n[INFO] Submitting transaction...')
    try:
        # CRITICAL: web3.py expects bytes objects for bytes calldata parameters, not hex strings
        # ethers.js hexlify() returns hex string, but web3.py encodes bytes objects correctly
        # Passing hex string to web3.py can cause double-encoding issues
        
        # First, simulate the call to check for errors
        print('   [INFO] Simulating transaction call...')
        try:
            result = contract.functions.storeRecipe(
                recipe_root,
                compressed["bytes"],  # Hex string format (matches JS)
                True,  # canCreateNFTs
                True,  # isPublic
                COMPRESSION_GZIP,
                recipe_name,
                recipe_description
            ).call({'from': signer_account.address})
            print(f'   [SUCCESS] Simulation succeeded, would return recipe ID: {result}')
        except Exception as sim_error:
            error_msg = str(sim_error)
            print(f'   [WARNING] Simulation failed: {error_msg}')
            if 'not recipe creator' in error_msg.lower() or 'RECIPE_CREATOR_ROLE' in error_msg:
                print('\n   [ERROR] Your wallet lacks RECIPE_CREATOR_ROLE.')
                print('   Contact admin to get access.')
                return False
            # Continue anyway - simulation might fail for other reasons
        
        # Build and send actual transaction
        print('   [INFO] Building transaction...')
        
        # Estimate gas first (like ethers.js does automatically)
        try:
            gas_estimate = contract.functions.storeRecipe(
                recipe_root,
                compressed["bytes"],  # Hex string format
                True,
                True,
                COMPRESSION_GZIP,
                recipe_name,
                recipe_description
            ).estimate_gas({'from': signer_account.address})
            print(f'   [INFO] Gas estimate: {gas_estimate}')
            # Add 20% buffer
            gas_limit = int(gas_estimate * 1.2)
        except Exception as e:
            print(f'   [WARNING] Gas estimation failed: {e}, using default 500000')
            gas_limit = 500000
        
        # Use hex string format to match JS ethers.hexlify() exactly
        tx = contract.functions.storeRecipe(
            recipe_root,
            compressed["bytes"],  # Hex string format (e.g., "0x1f8b08...") - matches JS
            True,  # canCreateNFTs
            True,  # isPublic
            COMPRESSION_GZIP,
            recipe_name,
            recipe_description
        ).build_transaction({
            'from': signer_account.address,
            'nonce': w3.eth.get_transaction_count(signer_account.address),
            'gas': gas_limit,
        })
        
        print('   [INFO] Signing transaction...')
        # Sign and send
        signed_tx = signer_account.sign_transaction(tx)
        print('   [INFO] Sending transaction...')
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f'   Transaction hash: {tx_hash.hex()}')
        print('   [PENDING] Waiting for confirmation...')
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        # Check transaction status
        if receipt['status'] == 0:
            print(f'\n[ERROR] Transaction failed (reverted)!')
            print(f'   Block: {receipt["blockNumber"]}')
            print(f'   Gas Used: {receipt["gasUsed"]}')
            print(f'\n   Check the transaction receipt for more details:')
            print(f'   https://basescan.org/tx/{tx_hash.hex()}')
            
            # Try to get revert reason if available
            error_msg = str(receipt.get('revertReason', ''))
            if 'not recipe creator' in error_msg.lower() or 'RECIPE_CREATOR_ROLE' in error_msg:
                print('\n   Your wallet lacks RECIPE_CREATOR_ROLE.')
                print('   Contact admin to get access.')
            
            return False
        
        print(f'   [SUCCESS] Confirmed in block {receipt["blockNumber"]}')
        print(f'   Gas used: {receipt["gasUsed"]}')
        
        # Extract recipe ID from event
        recipe_id = None
        for log in receipt['logs']:
            try:
                parsed = contract.events.RecipeStored().process_log(log)
                recipe_id = parsed['args']['recipeId']
                break
            except Exception:
                continue
        
        if recipe_id:
            print(f'\n[SUCCESS] Recipe Stored!')
            print(f'   Recipe ID: {recipe_id}')
            print(f'   Creator: {signer_address}')
        else:
            print(f'\n[WARNING] Could not extract recipe ID from events')
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f'\n[ERROR] Transaction failed: {error_msg}')
        
        if 'not recipe creator' in error_msg.lower() or 'RECIPE_CREATOR_ROLE' in error_msg:
            print('\n   Your wallet lacks RECIPE_CREATOR_ROLE.')
            print('   Contact admin to get access.')
        
        import traceback
        traceback.print_exc()
        return False
    
    print('\n' + '=' * 60)
    print('   Recipe added successfully!')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
