#!/bin/bash
#
# Test script for ltx2_i2v (image-to-video) jobs via AI PowerGrid
#
# Usage:
#   ./test_ltx2_i2v.sh <image_path> [prompt]
#
# Prerequisites:
#   1. Get API key from https://dashboard.aipowergrid.io
#   2. Set environment variable: export API_KEY="your-api-key"
#   3. Have comfy-bridge worker running to process the job
#   4. Required tools: curl, base64, jq

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-https://api.aipowergrid.io/api}"
API_KEY="${API_KEY:-}"
POLL_INTERVAL=5
TIMEOUT=600

# Parse arguments
IMAGE_PATH="$1"
PROMPT="${2:-A gentle breeze animates the scene, subtle movement brings life to the image}"
NEGATIVE_PROMPT="${3:-blurry, low quality, still frame, frames, watermark, overlay, titles}"

# Validate inputs
if [ -z "$IMAGE_PATH" ]; then
    echo -e "${RED}Usage: $0 <image_path> [prompt] [negative_prompt]${NC}"
    echo ""
    echo "Example:"
    echo "  $0 ./test_image.png \"A woman smiles and waves hello\""
    exit 1
fi

if [ -z "$API_KEY" ]; then
    echo -e "${RED}ERROR: API_KEY environment variable not set${NC}"
    echo -e "${YELLOW}Get your API key from https://dashboard.aipowergrid.io${NC}"
    echo "Then run: export API_KEY=\"your-api-key\""
    exit 1
fi

if [ ! -f "$IMAGE_PATH" ]; then
    echo -e "${RED}ERROR: Image file not found: $IMAGE_PATH${NC}"
    exit 1
fi

# Check for required tools
for tool in curl base64 jq; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}ERROR: Required tool '$tool' not found${NC}"
        exit 1
    fi
done

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  LTX2 Image-to-Video Test Script${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Convert image to base64 (with auto-resize if needed)
echo -e "${YELLOW}Loading image: $IMAGE_PATH${NC}"
IMAGE_SIZE=$(ls -lh "$IMAGE_PATH" | awk '{print $5}')
echo -e "${GRAY}  File size: $IMAGE_SIZE${NC}"

# Check if image needs resizing (API max is 3072x3072, we use 2048 to be safe)
MAX_DIM=2048
TEMP_IMAGE=""
FINAL_IMAGE_PATH="$IMAGE_PATH"
RESIZE_DONE=false

# Function to resize using PowerShell (works on Windows)
resize_with_powershell() {
    local input="$1"
    local output="$2"
    local max_dim="$3"
    
    # Convert path to Windows format for PowerShell
    local win_input=$(cygpath -w "$input" 2>/dev/null || echo "$input")
    local win_output=$(cygpath -w "$output" 2>/dev/null || echo "$output")
    
    powershell.exe -NoProfile -Command "
        Add-Type -AssemblyName System.Drawing
        \$img = [System.Drawing.Image]::FromFile('$win_input')
        \$ratio = [Math]::Min($max_dim/\$img.Width, $max_dim/\$img.Height)
        if (\$ratio -lt 1) {
            \$newW = [int](\$img.Width * \$ratio)
            \$newH = [int](\$img.Height * \$ratio)
            \$bmp = New-Object System.Drawing.Bitmap(\$newW, \$newH)
            \$g = [System.Drawing.Graphics]::FromImage(\$bmp)
            \$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            \$g.DrawImage(\$img, 0, 0, \$newW, \$newH)
            \$bmp.Save('$win_output', [System.Drawing.Imaging.ImageFormat]::Jpeg)
            \$bmp.Dispose()
            \$g.Dispose()
            Write-Output \"\$newW x \$newH\"
        } else {
            Write-Output 'NO_RESIZE'
        }
        \$img.Dispose()
    " 2>/dev/null
}

# Function to get image dimensions using PowerShell
get_dimensions_powershell() {
    local input="$1"
    local win_input=$(cygpath -w "$input" 2>/dev/null || echo "$input")
    
    powershell.exe -NoProfile -Command "
        Add-Type -AssemblyName System.Drawing
        \$img = [System.Drawing.Image]::FromFile('$win_input')
        Write-Output \"\$(\$img.Width)x\$(\$img.Height)\"
        \$img.Dispose()
    " 2>/dev/null
}

# Try different methods to get dimensions and resize

# Method 1: ImageMagick (Linux/Mac/Windows with IM installed)
if command -v identify &> /dev/null && command -v convert &> /dev/null; then
    DIMENSIONS=$(identify -format "%wx%h" "$IMAGE_PATH" 2>/dev/null)
    WIDTH=$(echo "$DIMENSIONS" | cut -d'x' -f1)
    HEIGHT=$(echo "$DIMENSIONS" | cut -d'x' -f2)
    echo -e "${GRAY}  Dimensions: ${WIDTH}x${HEIGHT}${NC}"
    
    if [ "$WIDTH" -gt "$MAX_DIM" ] || [ "$HEIGHT" -gt "$MAX_DIM" ]; then
        echo -e "${YELLOW}  Image exceeds ${MAX_DIM}px, resizing with ImageMagick...${NC}"
        TEMP_IMAGE=$(mktemp --suffix=.jpg 2>/dev/null || echo "/tmp/ltx2_resize_$$.jpg")
        convert "$IMAGE_PATH" -resize "${MAX_DIM}x${MAX_DIM}>" -quality 90 "$TEMP_IMAGE"
        FINAL_IMAGE_PATH="$TEMP_IMAGE"
        NEW_DIMS=$(identify -format "%wx%h" "$TEMP_IMAGE" 2>/dev/null)
        NEW_SIZE=$(ls -lh "$TEMP_IMAGE" | awk '{print $5}')
        echo -e "${GREEN}  Resized to: ${NEW_DIMS} (${NEW_SIZE})${NC}"
        RESIZE_DONE=true
    fi

# Method 2: PowerShell (Windows - always available)
elif command -v powershell.exe &> /dev/null; then
    echo -e "${GRAY}  Using PowerShell for image processing...${NC}"
    DIMENSIONS=$(get_dimensions_powershell "$IMAGE_PATH")
    WIDTH=$(echo "$DIMENSIONS" | cut -d'x' -f1 | tr -d ' \r')
    HEIGHT=$(echo "$DIMENSIONS" | cut -d'x' -f2 | tr -d ' \r')
    echo -e "${GRAY}  Dimensions: ${WIDTH}x${HEIGHT}${NC}"
    
    if [ "$WIDTH" -gt "$MAX_DIM" ] || [ "$HEIGHT" -gt "$MAX_DIM" ]; then
        echo -e "${YELLOW}  Image exceeds ${MAX_DIM}px, resizing with PowerShell...${NC}"
        TEMP_IMAGE="/tmp/ltx2_resize_$$.jpg"
        RESULT=$(resize_with_powershell "$IMAGE_PATH" "$TEMP_IMAGE" "$MAX_DIM")
        
        if [ "$RESULT" != "NO_RESIZE" ] && [ -f "$TEMP_IMAGE" ]; then
            FINAL_IMAGE_PATH="$TEMP_IMAGE"
            NEW_SIZE=$(ls -lh "$TEMP_IMAGE" | awk '{print $5}')
            echo -e "${GREEN}  Resized to: ${RESULT} (${NEW_SIZE})${NC}"
            RESIZE_DONE=true
        fi
    fi

# Method 3: Python with PIL (cross-platform fallback)
elif command -v python3 &> /dev/null || command -v python &> /dev/null; then
    PYTHON_CMD=$(command -v python3 || command -v python)
    
    # Check if PIL is available
    if $PYTHON_CMD -c "from PIL import Image" 2>/dev/null; then
        echo -e "${GRAY}  Using Python PIL for image processing...${NC}"
        
        DIMENSIONS=$($PYTHON_CMD -c "
from PIL import Image
img = Image.open('$IMAGE_PATH')
print(f'{img.width}x{img.height}')
" 2>/dev/null)
        WIDTH=$(echo "$DIMENSIONS" | cut -d'x' -f1)
        HEIGHT=$(echo "$DIMENSIONS" | cut -d'x' -f2)
        echo -e "${GRAY}  Dimensions: ${WIDTH}x${HEIGHT}${NC}"
        
        if [ "$WIDTH" -gt "$MAX_DIM" ] || [ "$HEIGHT" -gt "$MAX_DIM" ]; then
            echo -e "${YELLOW}  Image exceeds ${MAX_DIM}px, resizing with PIL...${NC}"
            TEMP_IMAGE="/tmp/ltx2_resize_$$.jpg"
            
            $PYTHON_CMD -c "
from PIL import Image
img = Image.open('$IMAGE_PATH')
ratio = min($MAX_DIM/img.width, $MAX_DIM/img.height)
if ratio < 1:
    new_size = (int(img.width * ratio), int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    img.save('$TEMP_IMAGE', 'JPEG', quality=90)
    print(f'{new_size[0]}x{new_size[1]}')
" 2>/dev/null
            
            if [ -f "$TEMP_IMAGE" ]; then
                FINAL_IMAGE_PATH="$TEMP_IMAGE"
                NEW_SIZE=$(ls -lh "$TEMP_IMAGE" | awk '{print $5}')
                echo -e "${GREEN}  Resized (${NEW_SIZE})${NC}"
                RESIZE_DONE=true
            fi
        fi
    fi

# Method 4: ffmpeg/ffprobe
elif command -v ffmpeg &> /dev/null && command -v ffprobe &> /dev/null; then
    DIMENSIONS=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$IMAGE_PATH" 2>/dev/null)
    WIDTH=$(echo "$DIMENSIONS" | cut -d',' -f1)
    HEIGHT=$(echo "$DIMENSIONS" | cut -d',' -f2)
    echo -e "${GRAY}  Dimensions: ${WIDTH}x${HEIGHT}${NC}"
    
    if [ "$WIDTH" -gt "$MAX_DIM" ] || [ "$HEIGHT" -gt "$MAX_DIM" ]; then
        echo -e "${YELLOW}  Image exceeds ${MAX_DIM}px, resizing with ffmpeg...${NC}"
        TEMP_IMAGE="/tmp/ltx2_resize_$$.jpg"
        ffmpeg -i "$IMAGE_PATH" -vf "scale='if(gt(iw,ih),${MAX_DIM},-2)':'if(gt(ih,iw),${MAX_DIM},-2)'" -q:v 2 "$TEMP_IMAGE" -y 2>/dev/null
        if [ -f "$TEMP_IMAGE" ]; then
            FINAL_IMAGE_PATH="$TEMP_IMAGE"
            NEW_SIZE=$(ls -lh "$TEMP_IMAGE" | awk '{print $5}')
            echo -e "${GREEN}  Resized (${NEW_SIZE})${NC}"
            RESIZE_DONE=true
        fi
    fi

else
    echo -e "${RED}  Error: No image processing tool available${NC}"
    echo -e "${YELLOW}  Cannot verify/resize image. API limit: 3072x3072 pixels${NC}"
    echo -e "${GRAY}  Please ensure your image is under 3072x3072 pixels${NC}"
fi

# Get base64 (different on macOS vs Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    IMAGE_BASE64=$(base64 -i "$FINAL_IMAGE_PATH" | tr -d '\n')
else
    IMAGE_BASE64=$(base64 -w 0 "$FINAL_IMAGE_PATH")
fi

# Clean up temp file if created
if [ -n "$TEMP_IMAGE" ] && [ -f "$TEMP_IMAGE" ]; then
    rm -f "$TEMP_IMAGE"
fi

echo -e "${GRAY}  Base64 length: ${#IMAGE_BASE64} chars${NC}"

# Prepare job payload
echo ""
echo -e "${YELLOW}Job Configuration:${NC}"
echo -e "${GRAY}  Model: ltx2_i2v${NC}"
echo -e "${GRAY}  Prompt: $PROMPT${NC}"
echo -e "${GRAY}  Resolution: 1280x768${NC}"
echo -e "${GRAY}  Steps: 20${NC}"
echo -e "${GRAY}  CFG Scale: 4.0${NC}"
echo -e "${GRAY}  Video Length: 121 frames (~5s)${NC}"
echo ""

# Submit job
echo -e "${YELLOW}Submitting job to $API_BASE_URL/v2/generate/async...${NC}"

RESPONSE=$(curl -s -X POST "$API_BASE_URL/v2/generate/async" \
    -H "Content-Type: application/json" \
    -H "apikey: $API_KEY" \
    -H "Client-Agent: comfy-bridge-test/1.0" \
    -d @- << EOF
{
    "prompt": "$PROMPT",
    "negative_prompt": "$NEGATIVE_PROMPT",
    "models": ["ltx2_i2v"],
    "nsfw": false,
    "censor_nsfw": true,
    "trusted_workers": true,
    "r2": true,
    "source_image": "$IMAGE_BASE64",
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
}
EOF
)

# Check for error
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Failed to submit job${NC}"
    echo -e "${RED}Response: $RESPONSE${NC}"
    exit 1
fi

# Grid API returns 'id' not 'jobId'
JOB_ID=$(echo "$RESPONSE" | jq -r '.id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}ERROR: No job ID returned${NC}"
    echo -e "${RED}Response: $RESPONSE${NC}"
    exit 1
fi

KUDOS=$(echo "$RESPONSE" | jq -r '.kudos // 0')
echo -e "${GREEN}Job submitted successfully!${NC}"
echo -e "${CYAN}  Job ID: $JOB_ID${NC}"
echo -e "${GRAY}  Kudos: $KUDOS${NC}"
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Waiting for job completion...${NC}"
echo -e "${GRAY}  (Worker must be running to process job)${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Poll for job completion
START_TIME=$(date +%s)
LAST_STATUS=""

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ $ELAPSED -gt $TIMEOUT ]; then
        echo ""
        echo -e "${RED}TIMEOUT: Job did not complete within $TIMEOUT seconds${NC}"
        echo -e "${YELLOW}Check if comfy-bridge worker is running${NC}"
        exit 1
    fi
    
    STATUS_RESPONSE=$(curl -s "$API_BASE_URL/v2/generate/status/$JOB_ID" \
        -H "Client-Agent: comfy-bridge-test/1.0" 2>/dev/null || echo '{"error": "connection failed"}')
    
    # Check for connection error
    if echo "$STATUS_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
        echo -e "${YELLOW}Warning: Failed to check status${NC}"
        sleep $POLL_INTERVAL
        continue
    fi
    
    # Grid API status fields
    IS_DONE=$(echo "$STATUS_RESPONSE" | jq -r '.done // false')
    FAULTED=$(echo "$STATUS_RESPONSE" | jq -r '.faulted // false')
    QUEUE_POS=$(echo "$STATUS_RESPONSE" | jq -r '.queue_position // 0')
    WAIT_TIME=$(echo "$STATUS_RESPONSE" | jq -r '.wait_time // 0')
    PROCESSING=$(echo "$STATUS_RESPONSE" | jq -r '.processing // 0')
    WAITING=$(echo "$STATUS_RESPONSE" | jq -r '.waiting // 0')
    
    # Determine status
    if [ "$FAULTED" == "true" ]; then
        STATUS="faulted"
    elif [ "$IS_DONE" == "true" ]; then
        STATUS="completed"
    elif [ "$PROCESSING" != "0" ]; then
        STATUS="processing"
    else
        STATUS="queued"
    fi
    
    # Print status if changed
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        TIMESTAMP=$(date +"%H:%M:%S")
        case "$STATUS" in
            "queued")
                echo -e "[$TIMESTAMP] Status: ${YELLOW}QUEUED${NC} (position: $QUEUE_POS, waiting: $WAITING, wait: ${WAIT_TIME}s)"
                ;;
            "processing")
                echo -e "[$TIMESTAMP] Status: ${BLUE}PROCESSING${NC} - Worker picked up job!"
                ;;
            "completed")
                echo -e "[$TIMESTAMP] Status: ${GREEN}COMPLETED!${NC}"
                ;;
            "faulted")
                echo -e "[$TIMESTAMP] Status: ${RED}FAULTED${NC} - Job failed"
                ;;
            *)
                echo -e "[$TIMESTAMP] Status: ${GRAY}$STATUS${NC}"
                ;;
        esac
        LAST_STATUS="$STATUS"
    fi
    
    # Check for completion
    if [ "$IS_DONE" == "true" ] && [ "$FAULTED" != "true" ]; then
        echo ""
        echo -e "${GREEN}============================================${NC}"
        echo -e "${GREEN}  VIDEO GENERATION COMPLETE!${NC}"
        echo -e "${GREEN}============================================${NC}"
        echo ""
        
        # Extract generation info (Grid API format)
        GENERATIONS=$(echo "$STATUS_RESPONSE" | jq -r '.generations[]' 2>/dev/null)
        
        if [ -n "$GENERATIONS" ]; then
            echo "$STATUS_RESPONSE" | jq -r '.generations[] | "Generation ID: \(.id)\n  Worker: \(.worker_name)\n  Seed: \(.seed)"'
            
            # Grid API returns video URL in 'video', 'img_url', or 'img' field
            VIDEO_URL=$(echo "$STATUS_RESPONSE" | jq -r '.generations[0].video // .generations[0].img_url // .generations[0].img // empty')
            
            if [ -n "$VIDEO_URL" ]; then
                echo ""
                echo -e "${YELLOW}VIDEO URL:${NC}"
                echo -e "${CYAN}$VIDEO_URL${NC}"
                
                # Try to open in browser
                echo ""
                if command -v xdg-open &> /dev/null; then
                    read -p "Open video in browser? (Y/n) " -r
                    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                        xdg-open "$VIDEO_URL"
                    fi
                elif command -v open &> /dev/null; then
                    read -p "Open video in browser? (Y/n) " -r
                    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                        open "$VIDEO_URL"
                    fi
                fi
            fi
        else
            echo -e "${YELLOW}No generations found in response${NC}"
        fi
        
        echo ""
        echo -e "${GRAY}Total time: ${ELAPSED} seconds${NC}"
        exit 0
    fi
    
    # Check for failure
    if [ "$FAULTED" == "true" ] || [ "$STATUS" == "faulted" ]; then
        echo ""
        echo -e "${RED}ERROR: Job faulted!${NC}"
        echo "$STATUS_RESPONSE" | jq .
        exit 1
    fi
    
    sleep $POLL_INTERVAL
done
