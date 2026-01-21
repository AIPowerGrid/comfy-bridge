#!/bin/bash
# Simple curl command to test image generation via Grid API
# Replace YOUR_API_KEY with your actual API key

curl -X POST "https://api.aipowergrid.io/api/v2/generate/async" \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY" \
  -H "Client-Agent: comfy-bridge-test/1.0" \
  -d '{
    "prompt": "A beautiful sunset over mountains, cinematic lighting",
    "negative_prompt": "blurry, low quality, distorted",
    "models": ["flux.1-krea-dev"],
    "nsfw": false,
    "censor_nsfw": true,
    "trusted_workers": true,
    "r2": true,
    "shared": false,
    "params": {
      "width": 1024,
      "height": 1024,
      "steps": 25,
      "cfg_scale": 3.5,
      "sampler_name": "k_euler",
      "scheduler": "simple",
      "denoise": 1.0
    }
  }'
