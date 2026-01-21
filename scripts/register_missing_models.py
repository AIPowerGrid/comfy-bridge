#!/usr/bin/env python3
"""
Register Missing Models to Blockchain

This script registers the missing models (wan2.2-t2v-a14b, wan2.2-t2v-a14b-hq, ltxv)
directly to the ModelVault contract on Base Mainnet.

Usage:
    python scripts/register_missing_models.py [--dry-run]

Environment variables:
    PRIVATE_KEY - Private key with registrar role on ModelRegistry
    MODELVAULT_CONTRACT - ModelRegistry contract address (optional)
    MODELVAULT_RPC_URL - RPC URL (optional, defaults to Base Mainnet)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Error: web3 and eth-account packages required")
    print("Install with: pip install web3 eth-account")
    sys.exit(1)

# Contract configuration
CONTRACT_ADDRESS = os.getenv('MODELVAULT_CONTRACT', '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609')
RPC_URL = os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')
PRIVATE_KEY = os.getenv('PRIVATE_KEY') or os.getenv('WALLET_PRIVATE_KEY')

# Model type enum
MODEL_TYPE = {
    'TEXT': 0,
    'IMAGE': 1,
    'VIDEO': 2
}

# ABI for ModelVault
ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "modelHash", "type": "bytes32"},
            {"internalType": "uint8", "name": "modelType", "type": "uint8"},
            {"internalType": "string", "name": "fileName", "type": "string"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "version", "type": "string"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "string", "name": "downloadUrl", "type": "string"},
            {"internalType": "uint256", "name": "sizeBytes", "type": "uint256"},
            {"internalType": "string", "name": "quantization", "type": "string"},
            {"internalType": "string", "name": "format", "type": "string"},
            {"internalType": "uint32", "name": "vramMB", "type": "uint32"},
            {"internalType": "string", "name": "baseModel", "type": "string"},
            {"internalType": "bool", "name": "inpainting", "type": "bool"},
            {"internalType": "bool", "name": "img2img", "type": "bool"},
            {"internalType": "bool", "name": "controlnet", "type": "bool"},
            {"internalType": "bool", "name": "lora", "type": "bool"},
            {"internalType": "bool", "name": "isNSFW", "type": "bool"}
        ],
        "name": "registerModel",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getModelCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Models to register
MODELS_TO_REGISTER = [
    {
        'display_name': 'wan2.2-t2v-a14b',
        'file_name': 'wan2.2_t2v_14B.safetensors',
        'model_type': MODEL_TYPE['VIDEO'],
        'version': '2.2',
        'ipfs_cid': '',
        'download_url': '',  # Add if available
        'size_bytes': 28_000_000_000,  # ~28GB
        'quantization': 'fp8',
        'format': 'safetensors',
        'vram_mb': 48000,
        'base_model': 'wan_2_2',
        'inpainting': False,
        'img2img': True,
        'controlnet': False,
        'lora': False,
        'is_nsfw': False,
    },
    {
        'display_name': 'wan2.2-t2v-a14b-hq',
        'file_name': 'wan2.2_t2v_14B_hq.safetensors',
        'model_type': MODEL_TYPE['VIDEO'],
        'version': '2.2',
        'ipfs_cid': '',
        'download_url': '',
        'size_bytes': 28_000_000_000,
        'quantization': 'fp16',
        'format': 'safetensors',
        'vram_mb': 48000,
        'base_model': 'wan_2_2',
        'inpainting': False,
        'img2img': True,
        'controlnet': False,
        'lora': False,
        'is_nsfw': False,
    },
    {
        'display_name': 'ltxv',
        'file_name': 'ltx-video-2b-v0.9.safetensors',
        'model_type': MODEL_TYPE['VIDEO'],
        'version': '0.9',
        'ipfs_cid': '',
        'download_url': 'https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors',
        'size_bytes': 4_800_000_000,  # ~4.8GB
        'quantization': 'fp16',
        'format': 'safetensors',
        'vram_mb': 24000,
        'base_model': 'ltx_video',
        'inpainting': False,
        'img2img': True,
        'controlnet': False,
        'lora': False,
        'is_nsfw': False,
    },
    {
        'display_name': 'ltx2_i2v',
        'file_name': 'ltxv-13b-0.9.7-dev-fp8.safetensors',
        'model_type': MODEL_TYPE['VIDEO'],
        'version': '2.0',
        'ipfs_cid': '',
        'download_url': '',
        'size_bytes': 13_000_000_000,  # ~13GB
        'quantization': 'fp8',
        'format': 'safetensors',
        'vram_mb': 24000,
        'base_model': 'ltx_video_2',
        'inpainting': False,
        'img2img': True,  # Image-to-video
        'controlnet': False,
        'lora': False,
        'is_nsfw': False,
    },
]


def calculate_model_hash(file_name: str) -> str:
    """Calculate model hash from filename (keccak256)."""
    return Web3.keccak(text=file_name).hex()


def register_model(w3, contract, signer_account, model_data, dry_run=False):
    """Register a single model to the blockchain."""
    print(f"\nRegistering: {model_data['display_name']}")
    print(f"   File: {model_data['file_name']}")
    print(f"   Type: {'VIDEO' if model_data['model_type'] == MODEL_TYPE['VIDEO'] else 'IMAGE'}")
    print(f"   Size: {model_data['size_bytes'] / (1024**3):.2f} GB")
    
    model_hash = calculate_model_hash(model_data['file_name'])
    print(f"   Hash: {model_hash}")
    
    if dry_run:
        print(f"   [DRY RUN] Would register model")
        return True
    
    try:
        # Ensure model_hash is properly formatted as bytes32 (32 bytes)
        if model_hash.startswith('0x'):
            model_hash_bytes = bytes.fromhex(model_hash[2:])
        else:
            model_hash_bytes = bytes.fromhex(model_hash)
        
        # Ensure exactly 32 bytes
        if len(model_hash_bytes) != 32:
            print(f"   Error: Model hash must be exactly 32 bytes, got {len(model_hash_bytes)}")
            return False
        
        # Build transaction
        tx = contract.functions.registerModel(
            model_hash_bytes,  # bytes32 as bytes
            model_data['model_type'],
            model_data['file_name'],
            model_data['display_name'],
            model_data['version'],
            model_data['ipfs_cid'],
            model_data['download_url'],
            model_data['size_bytes'],
            model_data['quantization'],
            model_data['format'],
            model_data['vram_mb'],
            model_data['base_model'],
            model_data['inpainting'],
            model_data['img2img'],
            model_data['controlnet'],
            model_data['lora'],
            model_data['is_nsfw'],
        ).build_transaction({
            'from': signer_account.address,
            'nonce': w3.eth.get_transaction_count(signer_account.address),
            'gas': 500000,
        })
        
        # Sign and send
        signed_tx = signer_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"   Transaction sent: {tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"   Registered in block {receipt['blockNumber']}")
        
        return True
    except Exception as e:
        print(f"   Failed to register: {e}")
        return False


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='Register missing models to blockchain')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be registered without actually registering')
    args = parser.parse_args()
    
    print('Register Missing Models to Blockchain')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print(f'Contract: {CONTRACT_ADDRESS}')
    print()
    
    if args.dry_run:
        print('DRY RUN MODE - No transactions will be sent\n')
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('Failed to connect to blockchain')
        sys.exit(1)
    
    print(f'Connected to blockchain (Chain ID: {w3.eth.chain_id})')
    
    # Load contract
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)
    
    # Get current model count
    try:
        model_count = contract.functions.getModelCount().call()
        print(f'Current models on-chain: {model_count}\n')
    except Exception as e:
        print(f'Could not fetch model count: {e}')
        print('   Contract may not be deployed or RPC may be unavailable\n')
    
    # Check for private key (only required for actual registration)
    if not PRIVATE_KEY and not args.dry_run:
        print('PRIVATE_KEY environment variable required for registration')
        print('   Set PRIVATE_KEY in .env file or use --dry-run to preview')
        sys.exit(1)
    
    # Create signer if we have a private key
    signer_account = None
    if PRIVATE_KEY and not args.dry_run:
        try:
            signer_account = Account.from_key(PRIVATE_KEY)
            print(f'Signer: {signer_account.address}')
            
            balance = w3.eth.get_balance(signer_account.address)
            print(f'Balance: {w3.from_wei(balance, "ether")} ETH\n')
            
            if balance == 0:
                print('Warning: Signer has 0 ETH balance')
                print('   You need ETH on Base Mainnet to pay for gas fees\n')
        except Exception as e:
            print(f'Invalid private key: {e}')
            sys.exit(1)
    
    print(f'Models to register: {len(MODELS_TO_REGISTER)}\n')
    
    # Register each model
    success_count = 0
    fail_count = 0
    
    for model_data in MODELS_TO_REGISTER:
        if register_model(w3, contract, signer_account, model_data, dry_run=args.dry_run):
            success_count += 1
        else:
            fail_count += 1
        
        # Delay between transactions
        if not args.dry_run and model_data != MODELS_TO_REGISTER[-1]:
            import time
            time.sleep(2)
    
    print('\n' + '=' * 60)
    print(f'Summary: {success_count} registered, {fail_count} failed')
    
    if args.dry_run:
        print('\nRun without --dry-run to actually register these models')


if __name__ == '__main__':
    main()

