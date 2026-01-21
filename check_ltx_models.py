#!/usr/bin/env python3
"""Quick check for ltx2_i2v model status."""
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GRID_API_KEY')
api_url = os.getenv('GRID_API_URL', 'https://api.aipowergrid.io/api')

print(f"Checking {api_url}/v2/status/models...")
r = httpx.get(f'{api_url}/v2/status/models', headers={'apikey': api_key})
models = r.json()

print(f"\nFound {len(models)} models total")
print("\nLTX-related models:")
for m in models:
    name = m.get('name', '')
    if 'ltx' in name.lower() or 'i2v' in name.lower():
        print(f"  {name!r}: workers={m.get('count',0)}, queued={m.get('queued',0)}")

print("\nAll models with queued jobs:")
for m in models:
    queued = m.get('queued', 0)
    if queued > 0:
        print(f"  {m.get('name')!r}: workers={m.get('count',0)}, queued={queued}")

print("\nAll 6 models in API:")
for m in models:
    print(f"  {m.get('name')!r}: workers={m.get('count',0)}, queued={m.get('queued',0)}")
