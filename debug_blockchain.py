#!/usr/bin/env python3
"""Debug blockchain model fetching."""

import os
import sys
sys.path.insert(0, '/app/comfy-bridge')

from comfy_bridge.modelvault_client import ModelVaultClient
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Debugging Blockchain Model Fetching")
    print("=" * 60)
    
    # Initialize client with debugging
    client = ModelVaultClient(enabled=True)
    
    # Get total count directly
    print(f"\nDirect blockchain query:")
    total = client.get_total_models()
    print(f"Total models on chain: {total}")
    
    # Fetch all models with force refresh
    print(f"\nFetching all models with force_refresh=True...")
    models = client.fetch_all_models(force_refresh=True)
    print(f"Models fetched: {len(models)}")
    
    # Check specific models
    print("\n" + "=" * 60)
    print("Checking specific models:")
    print("=" * 60)
    
    target_models = {
        'wan2.2-t2v-a14b-hq': 'WAN 2.2 T2V 14B HQ',
        'wan2.2_ti2v_5B': 'WAN 2.2 TI2V 5B', 
        'ltxv': 'LTX Video',
        'flux.1-krea-dev': 'FLUX Krea Dev'
    }
    
    for model_id, description in target_models.items():
        found = model_id in models
        status = "✓ FOUND" if found else "✗ MISSING"
        print(f"\n{status}: {model_id} ({description})")
        
        if not found:
            # Check for similar names
            similar = []
            normalized = model_id.lower().replace('-','').replace('.','').replace('_','')
            
            for k in models.keys():
                k_norm = k.lower().replace('-','').replace('.','').replace('_','')
                if normalized in k_norm or k_norm in normalized:
                    similar.append(k)
            
            if similar:
                print(f"  Similar models found:")
                for s in similar[:5]:  # Show max 5 similar
                    print(f"    - {s}")
    
    # Show all WAN and LTX models
    print("\n" + "=" * 60)
    print("All WAN models in registry:")
    print("=" * 60)
    wan_models = [k for k in sorted(models.keys()) if 'wan' in k.lower()]
    for m in wan_models:
        print(f"  - {m}")
    
    print("\n" + "=" * 60)
    print("All LTX models in registry:")
    print("=" * 60)
    ltx_models = [k for k in sorted(models.keys()) if 'ltx' in k.lower()]
    if ltx_models:
        for m in ltx_models:
            print(f"  - {m}")
    else:
        print("  No LTX models found!")
        # Check if ltxv is in raw blockchain data
        print("\n  Checking if 'ltxv' exists with different casing...")
        for k in models.keys():
            if k.lower() == 'ltxv':
                print(f"    Found as: {k}")

if __name__ == "__main__":
    main()
