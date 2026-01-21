#!/usr/bin/env python3
"""List ALL models from Grid API."""
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GRID_API_KEY')
api_url = os.getenv('GRID_API_URL', 'https://api.aipowergrid.io/api')

# Get all models (not just active ones)
r = httpx.get(f'{api_url}/v2/status/models', headers={'apikey': api_key})
models = r.json()

print(f"Total models from /v2/status/models: {len(models)}")
for m in sorted(models, key=lambda x: x.get('name', '')):
    name = m.get('name', '')
    print(f"  {name}")

# Also check if there's a models endpoint
print("\nChecking /v2/models endpoint...")
try:
    r2 = httpx.get(f'{api_url}/v2/models', headers={'apikey': api_key})
    if r2.status_code == 200:
        data = r2.json()
        if isinstance(data, list):
            print(f"Found {len(data)} models")
            for m in data[:20]:
                if isinstance(m, dict):
                    print(f"  {m.get('name', m)}")
                else:
                    print(f"  {m}")
        else:
            print(f"Response: {data}")
    else:
        print(f"Status {r2.status_code}: {r2.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
