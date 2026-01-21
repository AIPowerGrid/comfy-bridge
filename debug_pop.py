#!/usr/bin/env python3
"""Debug pop_job to see why ltx2_i2v is rejected."""
import httpx
import os
import json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GRID_API_KEY')
api_url = os.getenv('GRID_API_URL', 'https://api.aipowergrid.io/api')
worker_name = os.getenv('GRID_WORKER_NAME', 'test-worker')

# Models to test
models = ['ltx2_i2v']

payload = {
    "name": worker_name,
    "models": models,
    "nsfw": True,
    "threads": 1,
    "max_pixels": 104857600,
    "bridge_agent": "comfy-bridge-debug",
}

print(f"Testing pop with models: {models}")
print(f"API URL: {api_url}/v2/generate/pop")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()

r = httpx.post(
    f'{api_url}/v2/generate/pop',
    headers={'apikey': api_key},
    json=payload,
    timeout=30
)

print(f"Status: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2)}")
