#!/bin/bash
#
# Simple curl example for ltx2_i2v (image-to-video) jobs
#
# This shows the raw curl commands needed to:
# 1. Submit an i2v job to the Grid API
# 2. Check job status
# 3. Get the video URL when complete
#
# For automated testing with polling, use test_ltx2_i2v.sh instead

# Configuration - UPDATE THESE VALUES
API_BASE_URL="${API_BASE_URL:-https://api.aipowergrid.io/api}"
API_KEY="${API_KEY:-your-api-key-here}"

echo "============================================"
echo "  LTX2 Image-to-Video - Curl Examples"
echo "  (Production Grid API)"
echo "============================================"
echo ""

# Example 1: Submit a job with inline base64 image
# In practice, you'd generate the base64 from a file:
#   IMAGE_BASE64=$(base64 -w 0 your_image.png)
#   Or on macOS: IMAGE_BASE64=$(base64 -i your_image.png | tr -d '\n')

echo "=== Example 1: Submit ltx2_i2v Job to Grid API ==="
echo ""
echo "# First, convert your image to base64:"
echo "IMAGE_BASE64=\$(base64 -w 0 your_image.png)"
echo ""
echo "# Then submit the job to production Grid API:"
cat << 'CURL_EXAMPLE'
curl -X POST "https://api.aipowergrid.io/api/v2/generate/async" \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY" \
  -H "Client-Agent: test-script/1.0" \
  -d '{
    "prompt": "A gentle breeze animates the scene, the subject smiles warmly",
    "negative_prompt": "blurry, low quality, still frame, watermark",
    "models": ["ltx2_i2v"],
    "nsfw": false,
    "censor_nsfw": true,
    "trusted_workers": true,
    "r2": true,
    "source_image": "BASE64_IMAGE_DATA_HERE",
    "source_processing": "img2video",
    "media_type": "video",
    "params": {
        "width": 1280,
        "height": 768,
      "steps": 20,
      "cfg_scale": 4.0,
      "length": 121,
      "fps": 25,
      "sampler_name": "k_euler"
    }
  }'
CURL_EXAMPLE

echo ""
echo "# Response will be like:"
echo '# {"id": "abc123-def456-...", "kudos": 10.5}'
echo ""

echo "=== Example 2: Check Job Status ==="
echo ""
cat << 'CURL_EXAMPLE'
curl -X GET "https://api.aipowergrid.io/api/v2/generate/status/YOUR_JOB_ID" \
  -H "Client-Agent: test-script/1.0"
CURL_EXAMPLE

echo ""
echo "# Response when queued:"
echo '# {"done": false, "faulted": false, "queue_position": 1, "waiting": 1, "processing": 0}'
echo ""
echo "# Response when processing:"
echo '# {"done": false, "faulted": false, "queue_position": 0, "waiting": 0, "processing": 1}'
echo ""
echo "# Response when completed:"
cat << 'EXAMPLE_RESPONSE'
# {
#   "done": true,
#   "faulted": false,
#   "finished": 1,
#   "processing": 0,
#   "waiting": 0,
#   "generations": [{
#     "id": "gen123",
#     "video": "https://images.aipg.art/gen123.mp4",
#     "seed": "12345",
#     "worker_name": "my-worker",
#     "worker_id": "worker-uuid"
#   }]
# }
EXAMPLE_RESPONSE
echo ""

echo "=== Example 3: One-liner with jq ==="
echo ""
echo "# Submit and extract job ID:"
cat << 'CURL_EXAMPLE'
JOB_ID=$(curl -s -X POST "https://api.aipowergrid.io/api/v2/generate/async" \
  -H "Content-Type: application/json" \
  -H "apikey: $API_KEY" \
  -H "Client-Agent: test-script/1.0" \
  -d '{"prompt": "...", "models": ["ltx2_i2v"], ...}' | jq -r '.id')

echo "Job ID: $JOB_ID"
CURL_EXAMPLE
echo ""

echo "=== Notes ==="
echo ""
echo "1. The ltx2_i2v model converts a single image to a ~5 second video"
echo "2. The 'sourceImage' must be raw base64 (no data:image/... prefix)"
echo "3. Video generation takes 2-5 minutes on a good GPU"
echo "4. The comfy-bridge worker must be running to process jobs"
echo "5. Video will be uploaded to R2 and URL returned in response"
echo ""
echo "Worker Processing Flow:"
echo "  1. Worker polls /v2/generate/pop for jobs with 'ltx2_i2v' model"
echo "  2. Worker downloads source_image and saves to ComfyUI input folder"
echo "  3. Worker runs ltx2_i2v.json workflow with image and prompt"
echo "  4. Worker uploads video to R2 and submits result to /v2/generate/submit"
echo "  5. API stores result and makes video URL available"
echo ""
