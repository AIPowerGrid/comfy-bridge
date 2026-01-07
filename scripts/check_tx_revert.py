#!/usr/bin/env python3
"""Check transaction revert reason."""

from web3 import Web3

RPC_URL = 'https://mainnet.base.org'
TX_HASH = '0x7db93786a906487c69e75d71d1a592ea1e8367556784669c36c8a7d858e4c48e'

w3 = Web3(Web3.HTTPProvider(RPC_URL))

try:
    receipt = w3.eth.get_transaction_receipt(TX_HASH)
    tx = w3.eth.get_transaction(TX_HASH)
    
    print(f"Transaction: {TX_HASH}")
    print(f"Status: {'SUCCESS' if receipt['status'] == 1 else 'FAILED'}")
    print(f"Block: {receipt['blockNumber']}")
    print(f"Gas Used: {receipt['gasUsed']}")
    
    if receipt['status'] == 0:
        print("\nTransaction failed. Attempting to get revert reason...")
        
        # Try to call the transaction to get revert reason
        try:
            # Replay the transaction as a call
            result = w3.eth.call({
                'to': tx['to'],
                'data': tx['input'],
                'from': tx['from'],
            }, receipt['blockNumber'] - 1)
            print("Call succeeded (unexpected)")
        except Exception as e:
            error_msg = str(e)
            print(f"Revert reason: {error_msg}")
            
            # Try to extract error message
            if "execution reverted" in error_msg.lower():
                if ":" in error_msg:
                    parts = error_msg.split(":", 1)
                    if len(parts) > 1:
                        print(f"Error details: {parts[1].strip()}")
except Exception as e:
    print(f"Error: {e}")

