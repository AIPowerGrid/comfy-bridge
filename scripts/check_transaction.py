#!/usr/bin/env python3
"""
Check Transaction Receipt

Check what actually happened in a transaction.

Usage:
    python scripts/check_transaction.py <tx-hash>
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

RPC_URL = os.getenv('RECIPESVAULT_RPC_URL') or os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_transaction.py <tx-hash>")
        sys.exit(1)
    
    tx_hash = sys.argv[1]
    
    print(f'Checking Transaction: {tx_hash}')
    print('=' * 60)
    print(f'RPC: {RPC_URL}')
    print()
    
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        sys.exit(1)
    
    print(f'[SUCCESS] Connected to blockchain (Chain ID: {w3.eth.chain_id})')
    
    # Get transaction receipt
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print(f'\n[INFO] Transaction Receipt:')
        print(f'  Block Number: {receipt["blockNumber"]}')
        print(f'  Status: {"SUCCESS" if receipt["status"] == 1 else "FAILED"}')
        print(f'  Gas Used: {receipt["gasUsed"]}')
        print(f'  From: {receipt["from"]}')
        print(f'  To: {receipt["to"]}')
        print(f'  Contract Address: {receipt["contractAddress"] or "N/A"}')
        
        if receipt["status"] == 0:
            print(f'\n[ERROR] Transaction failed!')
            print(f'  The transaction was reverted or failed.')
            
            # Try to get revert reason
            try:
                tx = w3.eth.get_transaction(tx_hash)
                # Try to call the function with same parameters to get revert reason
                print(f'\n[INFO] Attempting to decode revert reason...')
                # This is tricky - we'd need the contract instance and parameters
                # For now, just note common reasons
                print(f'  Common failure reasons:')
                print(f'    1. RecipeVault: paused (contract is paused)')
                print(f'    2. RecipeVault: recipe exists (recipe root already registered)')
                print(f'    3. RecipeVault: workflow too large (exceeds maxWorkflowBytes)')
                print(f'    4. RecipeVault: empty root (invalid recipe root)')
                print(f'    5. RecipeVault: empty workflow (workflow data is empty)')
                print(f'    6. Function not found (RecipeVault facet not registered in diamond)')
                print(f'    7. Access control (admin role required)')
            except Exception as e:
                pass
            
            return
        
        # Check for events
        print(f'\n[INFO] Events ({len(receipt["logs"])} logs):')
        
        # RecipeVault event ABI
        recipe_stored_abi = {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "recipeId", "type": "uint256"},
                {"indexed": True, "name": "recipeRoot", "type": "bytes32"},
                {"indexed": False, "name": "creator", "type": "address"}
            ],
            "name": "RecipeStored",
            "type": "event"
        }
        
        recipe_found = False
        for i, log in enumerate(receipt["logs"]):
            print(f'\n  Log {i+1}:')
            print(f'    Address: {log["address"]}')
            print(f'    Topics: {len(log["topics"])} topics')
            
            # Try to decode RecipeStored event
            try:
                # RecipeStored event signature
                event_signature = Web3.keccak(text="RecipeStored(uint256,bytes32,address)").hex()
                if log["topics"][0].hex() == event_signature:
                    recipe_id = int(log["topics"][1].hex(), 16)
                    recipe_root = log["topics"][2].hex()
                    creator = Web3.to_checksum_address("0x" + log["data"][-40:])
                    
                    print(f'    [SUCCESS] RecipeStored event found!')
                    print(f'      Recipe ID: {recipe_id}')
                    print(f'      Recipe Root: 0x{recipe_root}')
                    print(f'      Creator: {creator}')
                    recipe_found = True
            except Exception as e:
                pass
            
            # Show first topic (event signature)
            if log["topics"]:
                print(f'    Event Signature: {log["topics"][0].hex()}')
        
        if not recipe_found:
            print(f'\n[WARNING] No RecipeStored event found in transaction logs!')
            print(f'  This could mean:')
            print(f'    1. Recipe was not stored (transaction may have called wrong function)')
            print(f'    2. Event signature doesn\'t match')
            print(f'    3. RecipeVault facet is not handling the call correctly')
        
        # Get transaction details
        tx = w3.eth.get_transaction(tx_hash)
        print(f'\n[INFO] Transaction Details:')
        print(f'  Function Signature: {tx["input"][:10]}')
        print(f'  Input Data Length: {len(tx["input"])} bytes')
        
        # Try to decode function call
        # storeRecipe function signature: 0x... (need to calculate)
        store_recipe_sig = Web3.keccak(text="storeRecipe(bytes32,bytes,bool,bool,uint8,string,string)")[:4].hex()
        if tx["input"][:10] == "0x" + store_recipe_sig:
            print(f'  [SUCCESS] Function matches storeRecipe signature')
        else:
            print(f'  [WARNING] Function signature does not match storeRecipe')
            print(f'    Expected: 0x{store_recipe_sig}')
            print(f'    Got: {tx["input"][:10]}')
        
    except Exception as e:
        print(f'[ERROR] Failed to get transaction receipt: {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

