# PowerShell script for testing image generation via aipg-art-gallery API
# This script sends POST requests with all required parameters

# Configuration - Update these values
$API_BASE_URL = if ($env:API_BASE_URL) { $env:API_BASE_URL } else { "http://localhost:8080" }
$API_KEY = if ($env:API_KEY) { $env:API_KEY } else { "your-api-key-here" }
$MODEL_ID = if ($env:MODEL_ID) { $env:MODEL_ID } else { "flux.1-krea-dev" }

Write-Host "Testing Image Generation API" -ForegroundColor Green
Write-Host "=================================="
Write-Host "API URL: $API_BASE_URL"
Write-Host "Model: $MODEL_ID"
Write-Host ""

# Test 1: Basic image generation with minimal parameters
Write-Host "Test 1: Basic image generation (minimal parameters)" -ForegroundColor Yellow
$body1 = @{
    modelId = $MODEL_ID
    prompt = "A beautiful sunset over mountains"
    apiKey = $API_KEY
    params = @{
        width = 1024
        height = 1024
        steps = 20
        cfgScale = 3.5
    }
} | ConvertTo-Json -Depth 10

try {
    $response1 = Invoke-RestMethod -Uri "$API_BASE_URL/api/jobs" -Method Post -Body $body1 -ContentType "application/json"
    Write-Host "Response: $($response1 | ConvertTo-Json)" -ForegroundColor Green
    $jobId1 = $response1.jobId
    Write-Host "Job ID: $jobId1" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Response: $($_.Exception.Response)" -ForegroundColor Red
}
Write-Host ""

# Test 2: Full parameters (all workflow parameters)
Write-Host "Test 2: Full parameters (all workflow parameters)" -ForegroundColor Yellow
$body2 = @{
    modelId = $MODEL_ID
    prompt = "A stunning photorealistic landscape with mountains and lakes, cinematic lighting, highly detailed"
    negativePrompt = "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark"
    apiKey = $API_KEY
    params = @{
        width = 1024
        height = 1024
        steps = 25
        cfgScale = 3.5
        sampler = "euler"
        scheduler = "simple"
        denoise = 1.0
        seed = "12345"
    }
} | ConvertTo-Json -Depth 10

try {
    $response2 = Invoke-RestMethod -Uri "$API_BASE_URL/api/jobs" -Method Post -Body $body2 -ContentType "application/json"
    Write-Host "Response: $($response2 | ConvertTo-Json)" -ForegroundColor Green
    $jobId2 = $response2.jobId
    Write-Host "Job ID: $jobId2" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 3: Check job status
if ($jobId1) {
    Write-Host "Test 4: Check job status for Job ID: $jobId1" -ForegroundColor Yellow
    try {
        $status = Invoke-RestMethod -Uri "$API_BASE_URL/api/jobs/$jobId1" -Method Get
        Write-Host "Status: $($status | ConvertTo-Json -Depth 10)" -ForegroundColor Green
    } catch {
        Write-Host "Error checking status: $_" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "Tests completed!" -ForegroundColor Green
Write-Host ""
Write-Host "To check job status manually:"
Write-Host "  Invoke-RestMethod -Uri `"$API_BASE_URL/api/jobs/{jobId}`" -Method Get"
Write-Host ""
Write-Host "To use environment variables:"
Write-Host "  `$env:API_BASE_URL = 'http://localhost:8080'"
Write-Host "  `$env:API_KEY = 'your-api-key'"
Write-Host "  `$env:MODEL_ID = 'flux.1-krea-dev'"
Write-Host "  .\test_image_generation.ps1"
