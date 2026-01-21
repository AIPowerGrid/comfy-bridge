# PowerShell script for testing ltx2_i2v (image-to-video) jobs via AI PowerGrid
# 
# Usage:
#   .\test_ltx2_i2v.ps1 -ImagePath "path\to\image.png" [-Prompt "your prompt"]
#
# Prerequisites:
#   1. Get API key from https://dashboard.aipowergrid.io
#   2. Set environment variable: $env:API_KEY = "your-api-key"
#   3. Have comfy-bridge worker running to process the job

param(
    [Parameter(Mandatory=$true)]
    [string]$ImagePath,
    
    [string]$Prompt = "A gentle breeze animates the scene, subtle movement brings life to the image",
    
    [string]$NegativePrompt = "blurry, low quality, still frame, frames, watermark, overlay, titles",
    
    [string]$ApiBaseUrl = "https://api.aipowergrid.io/api",
    
    [string]$ApiKey = "",
    
    [int]$PollIntervalSeconds = 5,
    
    [int]$TimeoutSeconds = 600
)

# Configuration
$API_KEY = if ($ApiKey) { $ApiKey } elseif ($env:API_KEY) { $env:API_KEY } else { "" }

# Check for API key
if (-not $API_KEY) {
    Write-Host "ERROR: API key required. Set `$env:API_KEY or use -ApiKey parameter" -ForegroundColor Red
    Write-Host "Get your API key from https://dashboard.aipowergrid.io" -ForegroundColor Yellow
    exit 1
}

# Verify image file exists
if (-not (Test-Path $ImagePath)) {
    Write-Host "ERROR: Image file not found: $ImagePath" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LTX2 Image-to-Video Test Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Convert image to base64
Write-Host "Loading image: $ImagePath" -ForegroundColor Yellow
try {
    $imageBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $ImagePath))
    $imageBase64 = [Convert]::ToBase64String($imageBytes)
    
    # Get image info
    $imageSizeKB = [math]::Round($imageBytes.Length / 1024, 2)
    Write-Host "  Size: $imageSizeKB KB" -ForegroundColor Gray
    Write-Host "  Base64 length: $($imageBase64.Length) chars" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Failed to read image file: $_" -ForegroundColor Red
    exit 1
}

# Prepare job payload
$jobPayload = @{
    modelId = "ltx2_i2v"
    prompt = $Prompt
    negativePrompt = $NegativePrompt
    apiKey = $API_KEY
    sourceImage = $imageBase64
    sourceProcessing = "img2video"
    mediaType = "video"
    params = @{
        width = 1280
        height = 768
        steps = 20
        cfgScale = 4.0
        length = 121    # frames (approx 5 seconds at 25fps)
        fps = 25
    }
}

Write-Host ""
Write-Host "Job Configuration:" -ForegroundColor Yellow
Write-Host "  Model: ltx2_i2v" -ForegroundColor Gray
Write-Host "  Prompt: $Prompt" -ForegroundColor Gray
Write-Host "  Resolution: $($jobPayload.params.width)x$($jobPayload.params.height)" -ForegroundColor Gray
Write-Host "  Steps: $($jobPayload.params.steps)" -ForegroundColor Gray
Write-Host "  CFG Scale: $($jobPayload.params.cfgScale)" -ForegroundColor Gray
Write-Host "  Video Length: $($jobPayload.params.length) frames (~$([math]::Round($jobPayload.params.length / $jobPayload.params.fps, 1))s)" -ForegroundColor Gray
Write-Host ""

# Submit job
Write-Host "Submitting job to $ApiBaseUrl/v2/generate/async..." -ForegroundColor Yellow

# Build Grid API payload format
$gridPayload = @{
    prompt = $Prompt
    negative_prompt = $NegativePrompt
    models = @("ltx2_i2v")
    nsfw = $false
    censor_nsfw = $true
    trusted_workers = $true
    r2 = $true
    source_image = $imageBase64
    source_processing = "img2video"
    media_type = "video"
    params = @{
        width = 1280
        height = 768
        steps = 20
        cfg_scale = 4.0
        length = 121
        fps = 25
        sampler_name = "k_euler"
    }
}

$jsonPayload = $gridPayload | ConvertTo-Json -Depth 10 -Compress

try {
    $headers = @{
        "Content-Type" = "application/json"
        "apikey" = $API_KEY
        "Client-Agent" = "comfy-bridge-test/1.0"
    }
    
    $response = Invoke-RestMethod -Uri "$ApiBaseUrl/v2/generate/async" `
        -Method Post `
        -Body $jsonPayload `
        -Headers $headers `
        -ErrorAction Stop
    
    # Grid API returns 'id' not 'jobId'
    $jobId = $response.id
    Write-Host "Job submitted successfully!" -ForegroundColor Green
    Write-Host "  Job ID: $jobId" -ForegroundColor Cyan
    Write-Host "  Kudos: $($response.kudos)" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Failed to submit job" -ForegroundColor Red
    Write-Host "  Status: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
    Write-Host "  Message: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.ErrorDetails.Message) {
        Write-Host "  Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Waiting for job completion..." -ForegroundColor Cyan
Write-Host "  (Worker must be running to process job)" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Poll for job completion
$startTime = Get-Date
$lastStatus = ""

while ($true) {
    $elapsed = (Get-Date) - $startTime
    
    if ($elapsed.TotalSeconds -gt $TimeoutSeconds) {
        Write-Host ""
        Write-Host "TIMEOUT: Job did not complete within $TimeoutSeconds seconds" -ForegroundColor Red
        Write-Host "Check if comfy-bridge worker is running and processing jobs" -ForegroundColor Yellow
        exit 1
    }
    
    try {
        $status = Invoke-RestMethod -Uri "$ApiBaseUrl/v2/generate/status/$jobId" `
            -Method Get `
            -Headers @{"Client-Agent" = "comfy-bridge-test/1.0"} `
            -ErrorAction Stop
        
        # Grid API status response fields
        $isDone = $status.done
        $isFaulted = $status.faulted
        $queuePos = $status.queue_position
        $waitTime = [math]::Round($status.wait_time, 1)
        $processing = $status.processing
        $waiting = $status.waiting
        $finished = $status.finished
        
        # Determine status
        if ($isFaulted) {
            $currentStatus = "faulted"
        } elseif ($isDone) {
            $currentStatus = "completed"
        } elseif ($processing -gt 0) {
            $currentStatus = "processing"
        } else {
            $currentStatus = "queued"
        }
        
        # Only print if status changed
        if ($currentStatus -ne $lastStatus) {
            $timestamp = (Get-Date).ToString("HH:mm:ss")
            switch ($currentStatus) {
                "queued" { 
                    Write-Host "[$timestamp] Status: QUEUED (position: $queuePos, waiting: $waiting, wait: ${waitTime}s)" -ForegroundColor Yellow 
                }
                "processing" { 
                    Write-Host "[$timestamp] Status: PROCESSING - Worker picked up job!" -ForegroundColor Blue 
                }
                "completed" { 
                    Write-Host "[$timestamp] Status: COMPLETED!" -ForegroundColor Green 
                }
                "faulted" { 
                    Write-Host "[$timestamp] Status: FAULTED - Job failed" -ForegroundColor Red 
                }
                default { 
                    Write-Host "[$timestamp] Status: $currentStatus" -ForegroundColor Gray 
                }
            }
            $lastStatus = $currentStatus
        }
        
        # Check for completion
        if ($isDone -and -not $isFaulted) {
            Write-Host ""
            Write-Host "============================================" -ForegroundColor Green
            Write-Host "  VIDEO GENERATION COMPLETE!" -ForegroundColor Green
            Write-Host "============================================" -ForegroundColor Green
            Write-Host ""
            
            # Display generation info (Grid API uses 'generations' array)
            if ($status.generations -and $status.generations.Count -gt 0) {
                foreach ($gen in $status.generations) {
                    Write-Host "Generation ID: $($gen.id)" -ForegroundColor Cyan
                    Write-Host "  Worker: $($gen.worker_name)" -ForegroundColor Gray
                    Write-Host "  Seed: $($gen.seed)" -ForegroundColor Gray
                    
                    # Grid API returns video URL in 'img' field for videos, or check for video-specific fields
                    $videoUrl = if ($gen.video) { $gen.video } elseif ($gen.img_url) { $gen.img_url } else { $gen.img }
                    
                    if ($videoUrl) {
                        Write-Host ""
                        Write-Host "  VIDEO URL:" -ForegroundColor Yellow
                        Write-Host "  $videoUrl" -ForegroundColor Cyan
                        
                        # Open in browser
                        Write-Host ""
                        $openBrowser = Read-Host "Open video in browser? (Y/n)"
                        if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
                            Start-Process $videoUrl
                        }
                    }
                }
            } else {
                Write-Host "No generations found in response" -ForegroundColor Yellow
                Write-Host "Full response:" -ForegroundColor Gray
                Write-Host ($status | ConvertTo-Json -Depth 5) -ForegroundColor Gray
            }
            
            Write-Host ""
            Write-Host "Total time: $([math]::Round($elapsed.TotalSeconds, 1)) seconds" -ForegroundColor Gray
            exit 0
        }
        
        # Check for failure
        if ($isFaulted) {
            Write-Host ""
            Write-Host "ERROR: Job faulted!" -ForegroundColor Red
            Write-Host "Response: $($status | ConvertTo-Json -Depth 5)" -ForegroundColor Red
            exit 1
        }
        
    } catch {
        Write-Host "Warning: Failed to check status: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
    Start-Sleep -Seconds $PollIntervalSeconds
}
