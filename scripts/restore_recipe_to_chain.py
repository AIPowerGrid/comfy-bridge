#!/usr/bin/env python3
"""
Restore/Re-register Recipe/Workflow to RecipeVault on Blockchain

This script restores workflows/recipes in the RecipeVault contract
on Base Mainnet by setting isPublic=true and canCreateNFTs=true.
This undoes an unregistration.

IMPORTANT: updateRecipePermissions() requires ADMIN_ROLE or RECIPE_CREATOR_ROLE
Contact admin to get the role granted to your wallet.

Usage:
    python scripts/restore_recipe_to_chain.py --recipe-id <id>
    python scripts/restore_recipe_to_chain.py --recipe-root <root_hash>
    python scripts/restore_recipe_to_chain.py --recipe-id <id> --dry-run

Environment variables:
    PRIVATE_KEY - Private key with ADMIN_ROLE or RECIPE_CREATOR_ROLE
    RECIPESVAULT_CONTRACT - Grid Diamond contract address (optional, defaults to Grid Diamond)
    RECIPESVAULT_RPC_URL - RPC URL (optional, defaults to Base Mainnet)
"""

import os
import sys
import json
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

# Role hashes (keccak256 of role name)
RECIPE_CREATOR_ROLE = Web3.keccak(text='RECIPE_CREATOR_ROLE')
ADMIN_ROLE = Web3.keccak(text='ADMIN_ROLE')

# ABI for RecipeVault (through diamond proxy)
RECIPE_VAULT_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "recipeId", "type": "uint256"},
            {"internalType": "bool", "name": "canCreateNFTs", "type": "bool"},
            {"internalType": "bool", "name": "isPublic", "type": "bool"}
        ],
        "name": "updateRecipePermissions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "recipeId", "type": "uint256"}],
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
            {"indexed": False, "name": "canCreateNFTs", "type": "bool"},
            {"indexed": False, "name": "isPublic", "type": "bool"}
        ],
        "name": "RecipeUpdated",
        "type": "event"
    }
]


def get_recipe_by_id(contract, recipe_id) -> tuple:
    """Get recipe by ID (accepts string or int, converts to int for contract call)."""
    try:
        # Convert to int for contract call (handles both string and int)
        recipe_id_int = int(recipe_id)
        recipe = contract.functions.getRecipe(recipe_id_int).call()
        return recipe
    except ValueError:
        raise Exception(f"Invalid recipe ID format: {recipe_id} (must be a number)")
    except Exception as e:
        raise Exception(f"Failed to fetch recipe {recipe_id}: {e}")


def get_recipe_by_root(contract, recipe_root: str) -> tuple:
    """Get recipe by root hash."""
    try:
        # Convert hex string to bytes32 if needed
        if isinstance(recipe_root, str):
            if recipe_root.startswith('0x'):
                recipe_root_bytes = bytes.fromhex(recipe_root[2:])
            else:
                recipe_root_bytes = bytes.fromhex(recipe_root)
            # Pad to 32 bytes
            recipe_root_bytes = recipe_root_bytes[:32].ljust(32, b'\x00')
        else:
            recipe_root_bytes = recipe_root
        
        recipe = contract.functions.getRecipeByRoot(recipe_root_bytes).call()
        if recipe[0] == 0:
            raise Exception(f"Recipe not found for root: {recipe_root}")
        return recipe
    except Exception as e:
        raise Exception(f"Failed to fetch recipe by root {recipe_root}: {e}")


def format_recipe_info(recipe: tuple) -> dict:
    """Format recipe tuple into readable dict."""
    return {
        'recipeId': recipe[0],
        'recipeRoot': recipe[1].hex() if isinstance(recipe[1], bytes) else recipe[1],
        'creator': recipe[3],
        'canCreateNFTs': recipe[4],
        'isPublic': recipe[5],
        'compression': recipe[6],
        'createdAt': recipe[7],
        'name': recipe[8],
        'description': recipe[9]
    }


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='Restore workflow/recipe to RecipeVault')
    parser.add_argument('--recipe-id', '-i', type=str, help='Recipe ID to restore (as string)')
    parser.add_argument('--recipe-root', '-r', help='Recipe root hash to restore')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be restored without actually restoring')
    args = parser.parse_args()
    
    print('\n' + '=' * 60)
    print('AIPG RecipeVault - Restore Recipe to Blockchain')
    if args.dry_run:
        print('                    [DRY RUN MODE]')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print(f'Contract: {CONTRACT_ADDRESS}')
    print()
    
    if args.dry_run:
        print('[DRY RUN MODE] - No transactions will be sent\n')
    
    # Validate arguments
    if not args.recipe_id and not args.recipe_root:
        print('[ERROR] Must provide either --recipe-id or --recipe-root')
        sys.exit(1)
    
    if args.recipe_id and args.recipe_root:
        print('[ERROR] Provide either --recipe-id OR --recipe-root, not both')
        sys.exit(1)
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        sys.exit(1)
    
    network = w3.eth.chain_id
    print(f'[SUCCESS] Connected to blockchain (Chain ID: {network})')
    
    # Load contract
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=RECIPE_VAULT_ABI)
    
    # Check for private key (only required for actual restoration)
    if not PRIVATE_KEY and not args.dry_run:
        print('\n[ERROR] PRIVATE_KEY environment variable required for restoration')
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
    
    # Check role (if not dry run)
    if not args.dry_run and signer_address:
        print('\n[INFO] Checking permissions...')
        try:
            has_creator_role = contract.functions.hasRole(RECIPE_CREATOR_ROLE, signer_address).call()
            has_admin_role = contract.functions.hasRole(ADMIN_ROLE, signer_address).call()
            
            if has_creator_role:
                print('   [SUCCESS] Has RECIPE_CREATOR_ROLE')
            elif has_admin_role:
                print('   [SUCCESS] Has ADMIN_ROLE (can update recipes)')
            else:
                print('   [ERROR] Missing ADMIN_ROLE or RECIPE_CREATOR_ROLE')
                print('\n   Your wallet does not have permission to update recipes.')
                print('   Contact the admin to grant ADMIN_ROLE or RECIPE_CREATOR_ROLE to:')
                print(f'   {signer_address}')
                sys.exit(1)
        except Exception as e:
            print(f'   [WARNING] Could not check role: {e}')
            print('   Proceeding anyway...')
    
    # Fetch recipe
    print('\n[INFO] Fetching recipe...')
    try:
        if args.recipe_id:
            recipe = get_recipe_by_id(contract, args.recipe_id)
        else:
            recipe = get_recipe_by_root(contract, args.recipe_root)
        
        recipe_info = format_recipe_info(recipe)
        
        print(f'   Recipe ID: {recipe_info["recipeId"]}')
        print(f'   Name: {recipe_info["name"]}')
        print(f'   Description: {recipe_info["description"][:50]}...' if len(recipe_info["description"]) > 50 else f'   Description: {recipe_info["description"]}')
        print(f'   Creator: {recipe_info["creator"]}')
        print(f'   Current Status:')
        print(f'     - Can Create NFTs: {recipe_info["canCreateNFTs"]}')
        print(f'     - Is Public: {recipe_info["isPublic"]}')
        
        # Check if already restored
        if recipe_info["isPublic"] and recipe_info["canCreateNFTs"]:
            print('\n   [INFO] Recipe is already restored (isPublic=true, canCreateNFTs=true)')
            return
        
    except Exception as e:
        print(f'[ERROR] {e}')
        sys.exit(1)
    
    # Show what will happen
    print('\n[INFO] Restoration will set:')
    print('   - canCreateNFTs: true')
    print('   - isPublic: true')
    print('\n   This will make the recipe publicly available again.')
    
    if args.dry_run:
        print('\n' + '=' * 60)
        print('   [DRY RUN COMPLETE]')
        print('')
        print('   To submit, run without --dry-run:')
        if args.recipe_id:
            print(f'   python scripts/restore_recipe_to_chain.py --recipe-id {args.recipe_id}')
        else:
            print(f'   python scripts/restore_recipe_to_chain.py --recipe-root {args.recipe_root}')
        print('')
        print('   NOTE: Your wallet needs ADMIN_ROLE or RECIPE_CREATOR_ROLE')
        print('=' * 60 + '\n')
        return
    
    # Submit transaction
    print('\n[INFO] Submitting transaction...')
    try:
        # Simulate the call first
        print('   [INFO] Simulating transaction call...')
        try:
            contract.functions.updateRecipePermissions(
                recipe_info["recipeId"],
                True,   # canCreateNFTs = true
                True    # isPublic = true
            ).call({'from': signer_account.address})
            print('   [SUCCESS] Simulation succeeded')
        except Exception as sim_error:
            error_msg = str(sim_error)
            print(f'   [WARNING] Simulation failed: {error_msg}')
            if 'not admin' in error_msg.lower() or 'ADMIN_ROLE' in error_msg or 'RECIPE_CREATOR_ROLE' in error_msg:
                print('\n   [ERROR] Your wallet lacks required role.')
                print('   Contact admin to get access.')
                return False
            # Continue anyway - simulation might fail for other reasons
        
        # Estimate gas
        print('   [INFO] Estimating gas...')
        try:
            gas_estimate = contract.functions.updateRecipePermissions(
                recipe_info["recipeId"],
                True,
                True
            ).estimate_gas({'from': signer_account.address})
            print(f'   [INFO] Gas estimate: {gas_estimate}')
            gas_limit = int(gas_estimate * 1.2)
        except Exception as e:
            print(f'   [WARNING] Gas estimation failed: {e}, using default 200000')
            gas_limit = 200000
        
        # Build transaction
        print('   [INFO] Building transaction...')
        tx = contract.functions.updateRecipePermissions(
            recipe_info["recipeId"],
            True,   # canCreateNFTs = true
            True    # isPublic = true
        ).build_transaction({
            'from': signer_account.address,
            'nonce': w3.eth.get_transaction_count(signer_account.address),
            'gas': gas_limit,
        })
        
        print('   [INFO] Signing transaction...')
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
            
            error_msg = str(receipt.get('revertReason', ''))
            if 'not admin' in error_msg.lower() or 'ADMIN_ROLE' in error_msg or 'RECIPE_CREATOR_ROLE' in error_msg:
                print('\n   Your wallet lacks required role.')
                print('   Contact admin to get access.')
            
            return False
        
        print(f'   [SUCCESS] Confirmed in block {receipt["blockNumber"]}')
        print(f'   Gas used: {receipt["gasUsed"]}')
        
        # Verify the update
        print('\n[INFO] Verifying update...')
        updated_recipe = get_recipe_by_id(contract, recipe_info["recipeId"])
        updated_info = format_recipe_info(updated_recipe)
        
        if updated_info["isPublic"] and updated_info["canCreateNFTs"]:
            print('   [SUCCESS] Recipe successfully restored!')
            print(f'   - canCreateNFTs: {updated_info["canCreateNFTs"]}')
            print(f'   - isPublic: {updated_info["isPublic"]}')
        else:
            print('   [WARNING] Recipe restoration may not have taken effect')
            print(f'   - canCreateNFTs: {updated_info["canCreateNFTs"]}')
            print(f'   - isPublic: {updated_info["isPublic"]}')
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f'\n[ERROR] Transaction failed: {error_msg}')
        
        if 'not admin' in error_msg.lower() or 'ADMIN_ROLE' in error_msg or 'RECIPE_CREATOR_ROLE' in error_msg:
            print('\n   Your wallet lacks required role.')
            print('   Contact admin to get access.')
        
        import traceback
        traceback.print_exc()
        return False
    
    print('\n' + '=' * 60)
    print('   Recipe restored successfully!')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
