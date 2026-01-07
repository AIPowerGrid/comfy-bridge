#!/usr/bin/env python3
"""
Debug Recipe Registration - Check why registration failed

This script simulates the recipe registration call to get the exact revert reason.

Usage:
    python scripts/debug_recipe_registration.py --workflow ltxv.json
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
except ImportError:
    print("Error: web3 package required")
    print("Install with: pip install web3")
    sys.exit(1)

CONTRACT_ADDRESS = os.getenv('RECIPESVAULT_CONTRACT') or os.getenv('MODELVAULT_CONTRACT', '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609')
RPC_URL = os.getenv('RECIPESVAULT_RPC_URL') or os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')

COMPRESSION_GZIP = 1

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
        "inputs": [],
        "name": "paused",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
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


def compress_workflow(workflow_json: dict) -> bytes:
    """Compress workflow JSON using gzip."""
    json_string = json.dumps(workflow_json, sort_keys=True, separators=(',', ':'))
    return gzip.compress(json_string.encode('utf-8'))


def load_workflow_file(workflow_path: str) -> dict:
    """Load workflow JSON from file."""
    workflow_file = Path(workflow_path)
    
    if not workflow_file.is_absolute():
        possible_paths = [
            workflow_file,
            Path(__file__).parent.parent / "workflows" / workflow_file.name,
            Path(__file__).parent.parent / workflow_file,
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
    import argparse
    parser = argparse.ArgumentParser(description='Debug recipe registration')
    parser.add_argument('--workflow', '-w', default='ltxv.json', help='Workflow file')
    args = parser.parse_args()
    
    print('Debug Recipe Registration')
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
    
    # Check if paused
    try:
        paused = contract.functions.paused().call()
        print(f'\n[INFO] Contract paused: {paused}')
        if paused:
            print(f'[ERROR] RecipeVault is paused! Cannot register recipes.')
            sys.exit(1)
    except Exception as e:
        print(f'[WARNING] Could not check paused status: {e}')
    
    # Check max workflow bytes
    try:
        max_bytes = contract.functions.getMaxWorkflowBytes().call()
        print(f'[INFO] Max workflow bytes: {max_bytes}')
    except Exception as e:
        print(f'[WARNING] Could not check max workflow bytes: {e}')
        max_bytes = 0
    
    # Load workflow
    try:
        workflow_json = load_workflow_file(args.workflow)
        print(f'\n[SUCCESS] Loaded workflow from: {args.workflow}')
    except FileNotFoundError as e:
        print(f'[ERROR] {e}')
        sys.exit(1)
    
    # Calculate recipe root and compress
    recipe_root = calculate_recipe_root(workflow_json)
    compressed_data = compress_workflow(workflow_json)
    
    print(f'\n[INFO] Recipe details:')
    print(f'  Recipe Root: 0x{recipe_root.hex()}')
    print(f'  Original size: {len(json.dumps(workflow_json))} bytes')
    print(f'  Compressed size: {len(compressed_data)} bytes')
    
    if max_bytes > 0 and len(compressed_data) > max_bytes:
        print(f'\n[ERROR] Workflow too large!')
        print(f'  Compressed size: {len(compressed_data)} bytes')
        print(f'  Max allowed: {max_bytes} bytes')
        sys.exit(1)
    
    # Check if recipe already exists
    try:
        existing = contract.functions.getRecipeByRoot(recipe_root).call()
        if existing[0] > 0:
            print(f'\n[WARNING] Recipe already exists!')
            print(f'  Recipe ID: {existing[0]}')
            print(f'  Name: {existing[8]}')
            sys.exit(0)
    except Exception as e:
        print(f'[INFO] Recipe does not exist yet (or error checking): {e}')
    
    # Try to simulate the call
    print(f'\n[INFO] Simulating storeRecipe call...')
    try:
        # Use a test address (doesn't matter for simulation)
        test_address = "0x0000000000000000000000000000000000000000"
        
        result = contract.functions.storeRecipe(
            recipe_root,
            compressed_data,
            True,  # canCreateNFTs
            True,  # isPublic
            COMPRESSION_GZIP,
            "ltxv",
            "LTX-Video workflow"
        ).call({'from': test_address})
        
        print(f'[SUCCESS] Simulation succeeded!')
        print(f'  Would return recipe ID: {result}')
        
    except Exception as e:
        error_msg = str(e)
        print(f'\n[ERROR] Simulation failed!')
        print(f'  Error: {error_msg}')
        
        # Try to extract revert reason
        if "RecipeVault:" in error_msg:
            reason = error_msg.split("RecipeVault:")[-1].strip()
            print(f'\n[INFO] Revert reason: RecipeVault: {reason}')
        elif "execution reverted" in error_msg.lower():
            print(f'\n[INFO] Transaction would revert')
            print(f'  This is expected - we\'re simulating with a zero address')
            print(f'  The actual error may be different when called with a real address')
        else:
            print(f'\n[INFO] Could not extract specific revert reason')
            print(f'  Full error: {error_msg}')


if __name__ == '__main__':
    main()

