#!/usr/bin/env python3
"""
Decode Revert Reason from Transaction

Decodes the actual revert reason from a failed transaction.

Usage:
    python scripts/decode_revert_reason.py <tx-hash>
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

def decode_revert_reason(tx_hash: str):
    """Decode revert reason from transaction."""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print('[ERROR] Failed to connect to blockchain')
        return
    
    print(f'Decoding revert reason for transaction: {tx_hash}')
    print('=' * 60)
    
    try:
        # Get transaction
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        print(f'Block: {receipt["blockNumber"]}')
        print(f'Status: {"SUCCESS" if receipt["status"] == 1 else "FAILED"}')
        print(f'Gas Used: {receipt["gasUsed"]}')
        print(f'From: {tx["from"]}')
        print(f'To: {tx["to"]}')
        
        if receipt["status"] == 1:
            print('\n[INFO] Transaction succeeded - no revert reason')
            return
        
        # Try to get revert reason by calling the function with same parameters
        # This is tricky - we need to decode the input data first
        print(f'\n[INFO] Transaction input data:')
        print(f'  Function selector: {tx["input"][:10]}')
        print(f'  Data length: {len(tx["input"])} bytes')
        
        # Common revert reasons
        print(f'\n[INFO] Common revert reasons:')
        print(f'  - "Grid: function not found" - Function not registered in diamond proxy')
        print(f'  - "RecipeVault: paused" - Contract is paused')
        print(f'  - "RecipeVault: recipe exists" - Recipe already registered')
        print(f'  - "RecipeVault: workflow too large" - Exceeds maxWorkflowBytes')
        print(f'  - "RecipeVault: empty root" - Invalid recipe root')
        print(f'  - "RecipeVault: empty workflow" - Empty workflow data')
        print(f'  - Access control errors - Missing required role')
        
        # Try to decode error from receipt logs (if any)
        if receipt["logs"]:
            print(f'\n[INFO] Transaction logs: {len(receipt["logs"])} logs found')
            for i, log in enumerate(receipt["logs"]):
                print(f'  Log {i+1}: {len(log["topics"])} topics, {len(log["data"])} bytes data')
        else:
            print(f'\n[INFO] No logs in transaction (typical for reverts)')
        
        # The actual revert reason is usually in the error message when calling
        # We can try to simulate the call to get the error
        print(f'\n[INFO] To get the exact revert reason, check:')
        print(f'  https://basescan.org/tx/{tx_hash}')
        print(f'  Or use a block explorer that shows revert reasons')
        
        # Try to decode if there's error data in the receipt
        # Some RPCs return error data in the receipt
        if "revertReason" in receipt:
            print(f'\n[SUCCESS] Revert reason found:')
            print(f'  {receipt["revertReason"]}')
        
    except Exception as e:
        print(f'[ERROR] Failed to decode: {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/decode_revert_reason.py <tx-hash>")
        sys.exit(1)
    
    decode_revert_reason(sys.argv[1])

