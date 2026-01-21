#!/usr/bin/env python3
"""Check models registered on blockchain."""
import os
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3

RPC_URL = os.getenv('MODELVAULT_RPC_URL', 'https://mainnet.base.org')
CONTRACT = os.getenv('MODELVAULT_CONTRACT', '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609')

# ABI for reading models
ABI = [
    {
        "inputs": [],
        "name": "getModelCount",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256", "name": "modelId"}],
        "name": "getModelById",
        "outputs": [
            {"components": [
                {"name": "modelId", "type": "uint256"},
                {"name": "modelHash", "type": "bytes32"},
                {"name": "modelType", "type": "uint8"},
                {"name": "fileName", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "ipfsCid", "type": "string"},
                {"name": "downloadUrl", "type": "string"},
                {"name": "sizeBytes", "type": "uint256"},
                {"name": "quantization", "type": "string"},
                {"name": "format", "type": "string"},
                {"name": "vramMB", "type": "uint32"},
                {"name": "baseModel", "type": "string"},
                {"name": "inpainting", "type": "bool"},
                {"name": "img2img", "type": "bool"},
                {"name": "controlnet", "type": "bool"},
                {"name": "lora", "type": "bool"},
                {"name": "isNSFW", "type": "bool"},
                {"name": "creator", "type": "address"},
                {"name": "createdAt", "type": "uint256"},
            ], "type": "tuple"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
contract = w3.eth.contract(address=CONTRACT, abi=ABI)

count = contract.functions.getModelCount().call()
print(f"Total models on blockchain: {count}")
print("\nLooking for ltx-related models...")

for i in range(1, count + 1):
    try:
        model = contract.functions.getModelById(i).call()
        name = model[4]  # name field
        if 'ltx' in name.lower() or 'i2v' in name.lower():
            print(f"  ID {i}: name={name!r}, fileName={model[3]!r}, type={model[2]}")
    except Exception as e:
        pass

print("\nAll video models (type=2):")
for i in range(1, count + 1):
    try:
        model = contract.functions.getModelById(i).call()
        if model[2] == 2:  # VIDEO type
            print(f"  ID {i}: {model[4]!r}")
    except:
        pass
