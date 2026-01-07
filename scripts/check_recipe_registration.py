#!/usr/bin/env python3
"""
Check Recipe Registration on Blockchain

This script checks if a recipe is registered on-chain and verifies RecipeVault is accessible.

Usage:
    python scripts/check_recipe_registration.py [--recipe-root <root-hash>]
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
except ImportError:
    print("Error: web3 package required")
    print("Install with: pip install web3")
    sys.exit(1)

# Contract configuration
CONTRACT_ADDRESS = os.getenv('RECIPESVAULT_CONTRACT') or os.getenv('MODELVAULT_CONTRACT', '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609')
RPC_URL = os.getenv('RECIPESVAULT_RPC_URL') or os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')

# ABI for RecipeVault
RECIPE_VAULT_ABI = [
    {
        "inputs": [],
        "name": "getTotalRecipes",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
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
    }
]


def calculate_recipe_root(workflow_json: dict) -> bytes:
    """Calculate recipe root hash from workflow JSON."""
    json_string = json.dumps(workflow_json, sort_keys=True, separators=(',', ':'))
    return Web3.keccak(text=json_string)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Check recipe registration on blockchain')
    parser.add_argument('--recipe-root', help='Recipe root hash to check (hex string)')
    parser.add_argument('--workflow', help='Workflow file to calculate root from')
    args = parser.parse_args()
    
    print('Checking Recipe Registration on Blockchain')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print(f'Contract: {CONTRACT_ADDRESS}')
    print()
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        sys.exit(1)
    
    print(f'[SUCCESS] Connected to blockchain (Chain ID: {w3.eth.chain_id})')
    
    # Load contract
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=RECIPE_VAULT_ABI)
    
    # Check if RecipeVault facet is available
    print('\n[INFO] Checking RecipeVault facet availability...')
    try:
        total = contract.functions.getTotalRecipes().call()
        print(f'[SUCCESS] RecipeVault facet is available')
        print(f'[INFO] Total recipes on-chain: {total}')
    except Exception as e:
        error_msg = str(e)
        if "function not found" in error_msg.lower() or "could not decode" in error_msg.lower():
            print(f'[ERROR] RecipeVault facet not available in diamond proxy')
            print(f'   Error: {error_msg}')
            print(f'   This means RecipeVault module is not registered in the Grid diamond proxy')
            sys.exit(1)
        else:
            print(f'[ERROR] Failed to query RecipeVault: {e}')
            sys.exit(1)
    
    # Get recipe root
    recipe_root = None
    if args.recipe_root:
        if args.recipe_root.startswith('0x'):
            recipe_root = bytes.fromhex(args.recipe_root[2:])
        else:
            recipe_root = bytes.fromhex(args.recipe_root)
    elif args.workflow:
        workflow_file = Path(args.workflow)
        
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
                print(f'[ERROR] Workflow file not found: {args.workflow}')
                print(f'   Tried:')
                for path in possible_paths:
                    print(f'     - {path}')
                sys.exit(1)
        
        if not workflow_file.exists():
            print(f'[ERROR] Workflow file not found: {workflow_file}')
            sys.exit(1)
            
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow_json = json.load(f)
        recipe_root = calculate_recipe_root(workflow_json)
        print(f'\n[INFO] Loaded workflow from: {workflow_file}')
        print(f'[INFO] Calculated recipe root from workflow: 0x{recipe_root.hex()}')
    
    # Check all recipes
    print(f'\n[INFO] Fetching all recipes from blockchain...')
    recipes_found = []
    if total > 0:
        for recipe_id in range(1, total + 1):
            try:
                recipe = contract.functions.getRecipe(recipe_id).call()
                recipe_id_val = recipe[0]
                recipe_root_val = recipe[1]
                recipe_name = recipe[8]
                recipe_desc = recipe[9]
                is_public = recipe[5]
                
                if recipe_id_val > 0:
                    root_hex = recipe_root_val.hex() if isinstance(recipe_root_val, bytes) else recipe_root_val
                    recipes_found.append({
                        'id': recipe_id_val,
                        'root': root_hex,
                        'name': recipe_name,
                        'description': recipe_desc,
                        'is_public': is_public
                    })
                    print(f'  Recipe {recipe_id_val}: {recipe_name}')
                    print(f'    Root: 0x{root_hex}')
                    print(f'    Public: {is_public}')
            except Exception as e:
                print(f'  [WARNING] Failed to fetch recipe {recipe_id}: {e}')
    else:
        print(f'  [INFO] No recipes found (total = 0)')
        print(f'  [INFO] This could mean:')
        print(f'    1. No recipes have been registered yet')
        print(f'    2. RecipeVault storage is not initialized')
        print(f'    3. Recipe was registered but count is not updating')
    
    print(f'\n[INFO] Found {len(recipes_found)} recipes on-chain')
    
    # Check specific recipe if provided
    if recipe_root:
        print(f'\n[INFO] Checking if recipe with root 0x{recipe_root.hex()} exists...')
        try:
            recipe = contract.functions.getRecipeByRoot(recipe_root).call()
            recipe_id = recipe[0]
            if recipe_id > 0:
                print(f'[SUCCESS] Recipe found!')
                print(f'  Recipe ID: {recipe_id}')
                print(f'  Name: {recipe[8]}')
                print(f'  Description: {recipe[9]}')
                print(f'  Public: {recipe[5]}')
                print(f'  Creator: {recipe[3]}')
                print(f'  Created At: {recipe[7]}')
                
                # If total is 0 but recipe exists, there's a counter issue
                if total == 0:
                    print(f'\n[WARNING] Recipe exists but getTotalRecipes() returned 0!')
                    print(f'  This suggests the RecipeVault counter is not initialized or not updating.')
                    print(f'  The recipe IS registered, but the count function may not be working correctly.')
            else:
                print(f'[WARNING] Recipe not found with root 0x{recipe_root.hex()}')
                print(f'  This recipe may not be registered yet, or the root hash is incorrect')
                print(f'  Registration transaction: 7021fe4713e1c4aa6f1ed019cf2a23d1eb61c7af319861348359ddd5b51222b5')
                print(f'  Check transaction receipt to verify if recipe was actually stored')
        except Exception as e:
            print(f'[ERROR] Failed to check recipe by root: {e}')
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()

