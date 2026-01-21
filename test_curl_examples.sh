#!/bin/bash

# Quick curl examples for testing image generation
# Usage: ./test_curl_examples.sh [api-url] [api-key]

API_BASE_URL="${1:-http://localhost:8080}"
API_KEY="${2:-your-api-key-here}"

echo "API Base URL: $API_BASE_URL"
echo "API Key: $API_KEY"
echo ""

# Example 1: Minimal request
echo "=== Example 1: Minimal Request ==="
curl -X POST "${API_BASE_URL}/api/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"modelId\": \"flux.1-krea-dev\",
    \"prompt\": \"A beautiful sunset\",
    \"apiKey\": \"${API_KEY}\",
    \"params\": {
      \"width\": 1024,
      \"height\": 1024,
      \"steps\": 20,
      \"cfgScale\": 3.5
    }
  }"
echo -e "\n"

# Example 2: Full parameters
echo "=== Example 2: Full Parameters ==="
curl -X POST "${API_BASE_URL}/api/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"modelId\": \"flux.1-krea-dev\",
    \"prompt\": \"A stunning photorealistic landscape\",
    \"negativePrompt\": \"blurry, low quality\",
    \"apiKey\": \"${API_KEY}\",
    \"params\": {
      \"width\": 1024,
      \"height\": 1024,
      \"steps\": 25,
      \"cfgScale\": 3.5,
      \"sampler\": \"euler\",
      \"scheduler\": \"simple\",
      \"denoise\": 1.0,
      \"seed\": \"12345\"
    }
  }"
echo -e "\n"

echo "Done! Use the jobId from responses to check status:"
echo "curl -X GET ${API_BASE_URL}/api/jobs/{jobId}"
