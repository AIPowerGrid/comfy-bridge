#!/bin/bash

# Test script for image generation via Grid API
# This script sends a POST request with all required parameters

# Configuration - Update these values
API_BASE_URL="${API_BASE_URL:-https://api.aipowergrid.io/api}"
API_KEY="${API_KEY:-your-api-key-here}"
MODEL_ID="${MODEL_ID:-flux.1-krea-dev}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Testing Image Generation API${NC}"
echo "=================================="
echo "API URL: $API_BASE_URL"
echo "Model: $MODEL_ID"
echo ""

# Test 1: Basic image generation with minimal parameters
echo -e "${YELLOW}Test 1: Basic image generation (minimal parameters)${NC}"
RESPONSE1=$(curl -s -X POST "${API_BASE_URL}/v2/generate/async" \
  -H "Content-Type: application/json" \
  -H "apikey: ${API_KEY}" \
  -H "Client-Agent: comfy-bridge-test/1.0" \
  -d '{
    "prompt": "A beautiful sunset over mountains",
    "negative_prompt": "",
    "models": ["'"$MODEL_ID"'"],
    "nsfw": false,
    "censor_nsfw": true,
    "trusted_workers": true,
    "r2": true,
    "shared": false,
    "params": {
      "width": 1024,
      "height": 768,
      "steps": 25,
      "cfg_scale": 3.5,
      "sampler_name": "k_euler",
      "scheduler": "simple"
    }
  }')

echo "Response: $RESPONSE1"
JOB_ID1=$(echo $RESPONSE1 | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
echo -e "${GREEN}Job ID: $JOB_ID1${NC}"
echo ""

# Test 2: Full parameters (all workflow parameters)
echo -e "${YELLOW}Test 2: Full parameters (all workflow parameters)${NC}"
RESPONSE2=$(curl -s -X POST "${API_BASE_URL}/v2/generate/async" \
  -H "Content-Type: application/json" \
  -H "apikey: ${API_KEY}" \
  -H "Client-Agent: comfy-bridge-test/1.0" \
  -d '{
    "prompt": "A stunning photorealistic landscape with mountains and lakes, cinematic lighting, highly detailed",
    "negative_prompt": "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark",
    "models": ["'"$MODEL_ID"'"],
    "nsfw": false,
    "censor_nsfw": true,
    "trusted_workers": true,
    "r2": true,
    "shared": false,
    "params": {
      "width": 1024,
      "height": 1024,
      "steps": 30,
      "cfg_scale": 3.5,
      "sampler_name": "k_euler",
      "scheduler": "simple",
      "denoise": 1.0,
      "seed": "54321"
    }
  }')

echo "Response: $RESPONSE2"
JOB_ID2=$(echo $RESPONSE2 | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
echo -e "${GREEN}Job ID: $JOB_ID2${NC}"
echo ""

# Test 3: Check job status
if [ ! -z "$JOB_ID1" ] && [ "$JOB_ID1" != "" ]; then
  echo -e "${YELLOW}Test 3: Check job status for Job ID: $JOB_ID1${NC}"
  sleep 2  # Wait a moment for job to be queued
  STATUS=$(curl -s -X GET "${API_BASE_URL}/v2/generate/status/${JOB_ID1}" \
    -H "Client-Agent: comfy-bridge-test/1.0")
  echo "Status: $STATUS"
  echo ""
fi

echo -e "${GREEN}Tests completed!${NC}"
echo ""
echo "To check job status manually:"
echo "  curl -X GET ${API_BASE_URL}/v2/generate/status/{jobId}"
echo ""
echo "To use environment variables:"
echo "  export API_BASE_URL=https://api.aipowergrid.io/api"
echo "  export API_KEY=your-api-key"
echo "  export MODEL_ID=flux.1-krea-dev"
echo "  ./test_image_generation.sh"
