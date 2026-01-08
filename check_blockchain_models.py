#!/usr/bin/env python3
"""Check if specific models are registered on the blockchain."""

import os
import sys
sys.path.insert(0, '/app/comfy-bridge')

from comfy_bridge.modelvault_client import ModelVaultClient

def main():
    print("Checking blockchain models...")
    client = ModelVaultClient(enabled=True)
    models = client.fetch_all_models(force_refresh=True)
    
    print(f"\nTotal models on blockchain: {len(models)}")
    print("\nAll model names on blockchain:")
    for name in sorted(models.keys()):
        print(f"  - {name}")
    
    print("\nChecking for specific models:")
    missing_models = ['wan2.2-t2v-a14b-hq', 'flux.1-krea-dev', 'ltxv']
    
    for name in missing_models:
        if name in models:
            print(f"✓ {name} found on blockchain")
        else:
            print(f"✗ {name} NOT found on blockchain")
            # Check for similar names
            similar = [k for k in models.keys() if name.lower() in k.lower() or k.lower() in name.lower()]
            if similar:
                print(f"  Similar names found: {similar}")

if __name__ == "__main__":
    main()
