#!/usr/bin/env python3
"""
List All Recipes from RecipeVault on Blockchain

This script lists all registered recipes from the RecipeVault contract
on Base Mainnet through the Grid Diamond proxy.

Usage:
    python scripts/list_recipes.py
    python scripts/list_recipes.py --detailed

Environment variables:
    RECIPESVAULT_CONTRACT - Grid Diamond contract address (optional, defaults to Grid Diamond)
    RECIPESVAULT_RPC_URL - RPC URL (optional, defaults to Base Mainnet)
"""

import os
import sys
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

# ABI for RecipeVault (through diamond proxy)
RECIPE_VAULT_ABI = [
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
        "inputs": [],
        "name": "getTotalRecipes",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def format_timestamp(timestamp: int) -> str:
    """Format Unix timestamp to readable date."""
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp)


def format_bytes(bytes_val: int) -> str:
    """Format bytes for display."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    return f"{bytes_val / (1024 * 1024):.2f} MB"


def get_recipe(contract, recipe_id: int) -> dict:
    """Get recipe by ID and format it."""
    try:
        recipe = contract.functions.getRecipe(recipe_id).call()
        return {
            'recipeId': recipe[0],
            'recipeRoot': recipe[1].hex() if isinstance(recipe[1], bytes) else recipe[1],
            'workflowDataSize': len(recipe[2]),
            'creator': recipe[3],
            'canCreateNFTs': recipe[4],
            'isPublic': recipe[5],
            'compression': recipe[6],
            'createdAt': recipe[7],
            'name': recipe[8],
            'description': recipe[9]
        }
    except Exception as e:
        return None


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='List all recipes from RecipeVault')
    parser.add_argument('--detailed', '-d', action='store_true',
                       help='Show detailed information for each recipe')
    args = parser.parse_args()
    
    print('\n' + '=' * 60)
    print('AIPG RecipeVault - List All Recipes')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print(f'Contract: {CONTRACT_ADDRESS}')
    print()
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        sys.exit(1)
    
    network = w3.eth.chain_id
    print(f'[SUCCESS] Connected to blockchain (Chain ID: {network})')
    
    # Load contract
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=RECIPE_VAULT_ABI)
    
    # Get total recipes
    print('\n[INFO] Fetching recipe count...')
    try:
        total_recipes = contract.functions.getTotalRecipes().call()
        print(f'   Total Recipes: {total_recipes}')
    except Exception as e:
        print(f'[ERROR] Failed to get total recipes: {e}')
        sys.exit(1)
    
    if total_recipes == 0:
        print('\n   No recipes found in RecipeVault.')
        return
    
    # Fetch all recipes
    print(f'\n[INFO] Fetching {total_recipes} recipes...')
    recipes = []
    failed_count = 0
    
    for recipe_id in range(1, total_recipes + 1):
        recipe = get_recipe(contract, recipe_id)
        if recipe:
            recipes.append(recipe)
        else:
            failed_count += 1
            if args.detailed:
                print(f'   [WARNING] Failed to fetch recipe {recipe_id}')
    
    if failed_count > 0:
        print(f'   [WARNING] Failed to fetch {failed_count} recipes')
    
    print(f'   [SUCCESS] Loaded {len(recipes)} recipes\n')
    
    # Display recipes
    print('=' * 60)
    print('RECIPES')
    print('=' * 60)
    
    if args.detailed:
        # Detailed view
        for i, recipe in enumerate(recipes, 1):
            print(f'\n[{i}/{len(recipes)}] Recipe ID: {recipe["recipeId"]}')
            print(f'   Name: {recipe["name"]}')
            print(f'   Description: {recipe["description"][:80]}...' if len(recipe["description"]) > 80 else f'   Description: {recipe["description"]}')
            print(f'   Creator: {recipe["creator"]}')
            print(f'   Recipe Root: {recipe["recipeRoot"][:20]}...')
            print(f'   Status:')
            print(f'     - Can Create NFTs: {recipe["canCreateNFTs"]}')
            print(f'     - Is Public: {recipe["isPublic"]}')
            print(f'   Workflow Data: {format_bytes(recipe["workflowDataSize"])}')
            print(f'   Compression: {recipe["compression"]} ({["None", "Gzip", "Brotli"][recipe["compression"]] if recipe["compression"] < 3 else "Unknown"})')
            print(f'   Created: {format_timestamp(recipe["createdAt"])}')
            print('   ' + '-' * 56)
    else:
        # Summary view
        print(f'\n{"ID":<8} {"Name":<30} {"Public":<8} {"NFTs":<8} {"Creator":<20}')
        print('-' * 60)
        
        for recipe in recipes:
            recipe_id_str = str(recipe["recipeId"])
            name = recipe["name"][:28] + '..' if len(recipe["name"]) > 30 else recipe["name"]
            is_public = "Yes" if recipe["isPublic"] else "No"
            can_nft = "Yes" if recipe["canCreateNFTs"] else "No"
            creator_short = recipe["creator"][:18] + '..' if len(recipe["creator"]) > 20 else recipe["creator"]
            
            print(f'{recipe_id_str:<8} {name:<30} {is_public:<8} {can_nft:<8} {creator_short:<20}')
    
    print('\n' + '=' * 60)
    print(f'Total: {len(recipes)} recipes')
    print('=' * 60)
    
    # Show usage examples
    print('\nTo unregister a recipe, use:')
    print(f'   python scripts/unregister_recipe_from_chain.py --recipe-id <id>')
    print('\nFor detailed view, use:')
    print(f'   python scripts/list_recipes.py --detailed')
    print()


if __name__ == '__main__':
    main()
