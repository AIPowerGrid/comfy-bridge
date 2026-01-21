#!/usr/bin/env python3
"""
Simple web interface for testing LTXV Image-to-Video.

Upload an image, see ComfyUI logs, get back the video.

Usage:
    python test_i2v_web.py
    
Then open http://localhost:5000 in your browser.
"""

import os
import sys
import json
import asyncio
import uuid
import time
import io
import threading
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from flask import Flask, request, jsonify, send_file, render_template_string
import httpx
import websockets

# Configuration
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8000")
WORKFLOW_DIR = os.path.join(os.path.dirname(__file__), "workflows")
OUTPUT_DIR = os.getenv("COMFYUI_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "output"))

app = Flask(__name__)

# Store logs and job status
job_logs = {}
job_status = {}
job_results = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LTXV Image-to-Video Test</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .upload-section {
            background: #16213e;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #aaa; }
        input[type="text"], textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #333;
            border-radius: 8px;
            background: #0f0f23;
            color: #fff;
            font-size: 14px;
        }
        textarea { min-height: 80px; resize: vertical; }
        input[type="file"] {
            padding: 15px;
            background: #0f0f23;
            border: 2px dashed #444;
            border-radius: 8px;
            width: 100%;
            cursor: pointer;
        }
        input[type="file"]:hover { border-color: #00d4ff; }
        button {
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: #000;
            border: none;
            padding: 15px 40px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
        }
        button:hover { opacity: 0.9; }
        button:disabled {
            background: #444;
            color: #888;
            cursor: not-allowed;
        }
        .preview-container {
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }
        .preview-box {
            flex: 1;
            background: #0f0f23;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .preview-box h3 { margin: 0 0 15px 0; color: #888; font-size: 14px; }
        .preview-box img, .preview-box video {
            max-width: 100%;
            max-height: 300px;
            border-radius: 8px;
        }
        #logs-section {
            background: #16213e;
            padding: 20px;
            border-radius: 12px;
            margin-top: 20px;
        }
        #logs-section h3 { margin: 0 0 15px 0; color: #00d4ff; }
        #logs {
            background: #0f0f23;
            border-radius: 8px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
        }
        .log-info { color: #00d4ff; }
        .log-progress { color: #00ff88; }
        .log-warning { color: #ffaa00; }
        .log-error { color: #ff4444; }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-waiting { background: #444; color: #aaa; }
        .status-processing { background: #0066cc; color: #fff; }
        .status-complete { background: #00aa44; color: #fff; }
        .status-error { background: #cc0000; color: #fff; }
        #download-btn {
            display: none;
            margin-top: 15px;
            background: linear-gradient(135deg, #00ff88, #00cc66);
        }
    </style>
</head>
<body>
    <h1>LTXV Image-to-Video</h1>
    <p class="subtitle">Upload an image and generate a video using LTX Video 2.0</p>
    
    <div class="upload-section">
        <form id="upload-form">
            <div class="form-group">
                <label>Source Image</label>
                <input type="file" id="image-input" accept="image/*" required>
            </div>
            <div class="form-group">
                <label>Prompt (describe the motion/action)</label>
                <textarea id="prompt-input" placeholder="A woman smiles and turns her head slowly...">A close-up shot of a person, their warm eyes meeting the camera with a gentle smile. Soft, warm light illuminates their features. The camera slowly pushes in toward their face. The mood is inviting and cinematic.</textarea>
            </div>
            <button type="submit" id="submit-btn">Generate Video</button>
        </form>
        
        <div class="preview-container">
            <div class="preview-box">
                <h3>INPUT IMAGE</h3>
                <img id="input-preview" src="" alt="Upload an image" style="display:none;">
            </div>
            <div class="preview-box">
                <h3>OUTPUT VIDEO <span id="status-badge" class="status-badge status-waiting">Waiting</span></h3>
                <video id="output-video" controls style="display:none;"></video>
                <button id="download-btn">Download Video</button>
            </div>
        </div>
    </div>
    
    <div id="logs-section">
        <h3>ComfyUI Logs</h3>
        <div id="logs">
            <div class="log-info">Ready. Upload an image to begin.</div>
        </div>
    </div>

    <script>
        const form = document.getElementById('upload-form');
        const imageInput = document.getElementById('image-input');
        const promptInput = document.getElementById('prompt-input');
        const submitBtn = document.getElementById('submit-btn');
        const inputPreview = document.getElementById('input-preview');
        const outputVideo = document.getElementById('output-video');
        const downloadBtn = document.getElementById('download-btn');
        const logsDiv = document.getElementById('logs');
        const statusBadge = document.getElementById('status-badge');
        
        let currentJobId = null;
        let pollInterval = null;
        
        // Preview uploaded image
        imageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    inputPreview.src = e.target.result;
                    inputPreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
        
        function addLog(message, type = 'info') {
            const div = document.createElement('div');
            div.className = 'log-' + type;
            div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            logsDiv.appendChild(div);
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function setStatus(status) {
            statusBadge.className = 'status-badge status-' + status;
            statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const file = imageInput.files[0];
            if (!file) {
                addLog('Please select an image first', 'warning');
                return;
            }
            
            // Reset UI
            logsDiv.innerHTML = '';
            outputVideo.style.display = 'none';
            downloadBtn.style.display = 'none';
            submitBtn.disabled = true;
            setStatus('processing');
            
            addLog('Starting image-to-video generation...', 'info');
            
            const formData = new FormData();
            formData.append('image', file);
            formData.append('prompt', promptInput.value);
            
            try {
                addLog('Uploading image to ComfyUI...', 'info');
                
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    addLog('Error: ' + data.error, 'error');
                    setStatus('error');
                    submitBtn.disabled = false;
                    return;
                }
                
                currentJobId = data.job_id;
                addLog(`Job started: ${currentJobId}`, 'info');
                addLog(`Prompt ID: ${data.prompt_id}`, 'info');
                
                // Start polling for status
                pollInterval = setInterval(() => pollStatus(currentJobId), 1000);
                
            } catch (err) {
                addLog('Error: ' + err.message, 'error');
                setStatus('error');
                submitBtn.disabled = false;
            }
        });
        
        async function pollStatus(jobId) {
            try {
                const response = await fetch(`/api/status/${jobId}`);
                const data = await response.json();
                
                // Add new logs
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(log => {
                        addLog(log.message, log.type || 'info');
                    });
                }
                
                if (data.status === 'complete') {
                    clearInterval(pollInterval);
                    addLog('Video generation complete!', 'progress');
                    setStatus('complete');
                    
                    // Show video
                    outputVideo.src = `/api/video/${jobId}?t=${Date.now()}`;
                    outputVideo.style.display = 'block';
                    downloadBtn.style.display = 'block';
                    downloadBtn.onclick = () => {
                        window.open(`/api/video/${jobId}?download=1`, '_blank');
                    };
                    
                    submitBtn.disabled = false;
                    
                } else if (data.status === 'error') {
                    clearInterval(pollInterval);
                    addLog('Error: ' + (data.error || 'Unknown error'), 'error');
                    setStatus('error');
                    submitBtn.disabled = false;
                }
                
            } catch (err) {
                // Ignore polling errors
            }
        }
    </script>
</body>
</html>
"""


def load_i2v_workflow():
    """Load the ltx2_i2v.json workflow."""
    workflow_path = os.path.join(WORKFLOW_DIR, "ltx2_i2v.json")
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_workflow_for_job(workflow, image_filename, prompt, seed=None):
    """Update workflow with job-specific parameters."""
    import random
    
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue
        
        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})
        
        # Set the input image
        if class_type == "LoadImage":
            inputs["image"] = image_filename
        
        # Set the prompt
        if class_type == "CLIPTextEncode":
            meta = node_data.get("_meta", {})
            title = meta.get("title", "").lower()
            if "positive" in title or "prompt" in title.lower():
                inputs["text"] = prompt
        
        # Set seed for RandomNoise nodes
        if class_type == "RandomNoise":
            if "noise_seed" in inputs:
                inputs["noise_seed"] = seed
    
    return workflow


async def upload_image_to_comfyui(image_data, filename):
    """Upload image to ComfyUI."""
    async with httpx.AsyncClient() as client:
        files = {"image": (filename, image_data, "image/png")}
        response = await client.post(f"{COMFYUI_URL}/upload/image", files=files)
        response.raise_for_status()
        return response.json()


async def submit_workflow(workflow):
    """Submit workflow to ComfyUI."""
    async with httpx.AsyncClient(timeout=30) as client:
        payload = {"prompt": workflow}
        response = await client.post(f"{COMFYUI_URL}/prompt", json=payload)
        response.raise_for_status()
        return response.json()


async def get_history(prompt_id):
    """Get workflow history from ComfyUI."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
        if response.status_code == 200:
            return response.json()
        return None


async def listen_to_websocket(prompt_id, job_id):
    """Listen to ComfyUI WebSocket for progress updates."""
    ws_url = COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws?clientId={job_id}"
    
    last_activity = time.time()
    
    try:
        async with websockets.connect(ws_url) as websocket:
            job_logs[job_id].append({"message": "Connected to ComfyUI WebSocket", "type": "info"})
            
            # Start a background task to poll for completion
            async def poll_for_completion():
                while job_status.get(job_id) == "processing":
                    await asyncio.sleep(3)
                    history = await get_history(prompt_id)
                    if history and prompt_id in history:
                        status_info = history[prompt_id].get("status", {})
                        if status_info.get("completed", False) or status_info.get("status_str") == "success":
                            job_logs[job_id].append({
                                "message": "Workflow execution complete (detected via polling)",
                                "type": "progress"
                            })
                            job_status[job_id] = "complete"
                            
                            # Find output file
                            outputs = history[prompt_id].get("outputs", {})
                            print(f"[DEBUG] Job {job_id} outputs: {json.dumps(outputs, indent=2)}")
                            for node_id, node_output in outputs.items():
                                if "videos" in node_output:
                                    video_info = node_output["videos"][0]
                                    job_results[job_id] = {
                                        "filename": video_info.get("filename"),
                                        "subfolder": video_info.get("subfolder", ""),
                                        "type": video_info.get("type", "output")
                                    }
                                    print(f"[DEBUG] Found video: {job_results[job_id]}")
                                    job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                                    return True
                                elif "gifs" in node_output:
                                    video_info = node_output["gifs"][0]
                                    job_results[job_id] = {
                                        "filename": video_info.get("filename"),
                                        "subfolder": video_info.get("subfolder", ""),
                                        "type": video_info.get("type", "output")
                                    }
                                    print(f"[DEBUG] Found gif: {job_results[job_id]}")
                                    job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                                    return True
                                elif "images" in node_output:
                                    # Some video nodes output as images (like animated webp)
                                    for img in node_output["images"]:
                                        if img.get("filename", "").endswith(('.mp4', '.webm', '.gif')):
                                            job_results[job_id] = {
                                                "filename": img.get("filename"),
                                                "subfolder": img.get("subfolder", ""),
                                                "type": img.get("type", "output")
                                            }
                                            print(f"[DEBUG] Found video in images: {job_results[job_id]}")
                                            job_logs[job_id].append({"message": f"Video saved: {img.get('filename')}", "type": "progress"})
                                            return True
                            print(f"[DEBUG] No video found in outputs")
                            return True
                return False
            
            poll_task = asyncio.create_task(poll_for_completion())
            
            async for message in websocket:
                # Check if job completed via polling
                if job_status.get(job_id) == "complete":
                    return
                
                # Skip binary messages (preview images)
                if isinstance(message, bytes):
                    continue
                
                last_activity = time.time()
                    
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "execution_start":
                        job_logs[job_id].append({"message": "Workflow execution started", "type": "progress"})
                    
                    elif msg_type == "progress":
                        progress_data = data.get("data", {})
                        current = progress_data.get("value", 0)
                        total = progress_data.get("max", 1)
                        pct = int((current / total) * 100) if total > 0 else 0
                        job_logs[job_id].append({
                            "message": f"Progress: {pct}% ({current}/{total})",
                            "type": "progress"
                        })
                    
                    elif msg_type == "executing":
                        node_id = data.get("data", {}).get("node")
                        prompt_id_msg = data.get("data", {}).get("prompt_id")
                        if node_id:
                            job_logs[job_id].append({
                                "message": f"Executing node: {node_id}",
                                "type": "info"
                            })
                        elif prompt_id_msg == prompt_id:
                            # Execution complete (node is null for our prompt)
                            job_logs[job_id].append({
                                "message": "Workflow execution complete",
                                "type": "progress"
                            })
                            job_status[job_id] = "complete"
                            
                            # Find output file
                            await asyncio.sleep(2)  # Wait for file to be written
                            history = await get_history(prompt_id)
                            if history and prompt_id in history:
                                outputs = history[prompt_id].get("outputs", {})
                                print(f"[DEBUG-WS] Job {job_id} outputs: {json.dumps(outputs, indent=2)}")
                                for node_id, node_output in outputs.items():
                                    if "videos" in node_output:
                                        video_info = node_output["videos"][0]
                                        job_results[job_id] = {
                                            "filename": video_info.get("filename"),
                                            "subfolder": video_info.get("subfolder", ""),
                                            "type": video_info.get("type", "output")
                                        }
                                        print(f"[DEBUG-WS] Found video: {job_results[job_id]}")
                                        job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                                        break
                                    elif "gifs" in node_output:
                                        video_info = node_output["gifs"][0]
                                        job_results[job_id] = {
                                            "filename": video_info.get("filename"),
                                            "subfolder": video_info.get("subfolder", ""),
                                            "type": video_info.get("type", "output")
                                        }
                                        print(f"[DEBUG-WS] Found gif: {job_results[job_id]}")
                                        job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                                        break
                                    elif "images" in node_output:
                                        for img in node_output["images"]:
                                            if img.get("filename", "").endswith(('.mp4', '.webm', '.gif')):
                                                job_results[job_id] = {
                                                    "filename": img.get("filename"),
                                                    "subfolder": img.get("subfolder", ""),
                                                    "type": img.get("type", "output")
                                                }
                                                print(f"[DEBUG-WS] Found video in images: {job_results[job_id]}")
                                                job_logs[job_id].append({"message": f"Video saved: {img.get('filename')}", "type": "progress"})
                                                break
                            poll_task.cancel()
                            return
                    
                    elif msg_type == "executed":
                        # Node finished executing
                        node_id = data.get("data", {}).get("node")
                        if node_id:
                            job_logs[job_id].append({
                                "message": f"Node {node_id} completed",
                                "type": "info"
                            })
                    
                    elif msg_type == "execution_cached":
                        # Some nodes were cached
                        nodes = data.get("data", {}).get("nodes", [])
                        if nodes:
                            job_logs[job_id].append({
                                "message": f"Cached nodes: {len(nodes)}",
                                "type": "info"
                            })
                    
                    elif msg_type == "execution_error":
                        error_data = data.get("data", {})
                        error_msg = error_data.get("exception_message", "Unknown error")
                        job_logs[job_id].append({
                            "message": f"Error: {error_msg}",
                            "type": "error"
                        })
                        job_status[job_id] = "error"
                        poll_task.cancel()
                        return
                    
                except json.JSONDecodeError:
                    pass
                    
    except Exception as e:
        job_logs[job_id].append({"message": f"WebSocket error: {str(e)}", "type": "warning"})
        # Fall back to polling
        job_logs[job_id].append({"message": "Falling back to polling for completion...", "type": "info"})
        while job_status.get(job_id) == "processing":
            await asyncio.sleep(3)
            history = await get_history(prompt_id)
            if history and prompt_id in history:
                status_info = history[prompt_id].get("status", {})
                if status_info.get("completed", False) or status_info.get("status_str") == "success":
                    job_logs[job_id].append({
                        "message": "Workflow execution complete",
                        "type": "progress"
                    })
                    job_status[job_id] = "complete"
                    outputs = history[prompt_id].get("outputs", {})
                    print(f"[DEBUG-FALLBACK] Job {job_id} outputs: {json.dumps(outputs, indent=2)}")
                    for node_id, node_output in outputs.items():
                        if "videos" in node_output:
                            video_info = node_output["videos"][0]
                            job_results[job_id] = {
                                "filename": video_info.get("filename"),
                                "subfolder": video_info.get("subfolder", ""),
                                "type": video_info.get("type", "output")
                            }
                            print(f"[DEBUG-FALLBACK] Found video: {job_results[job_id]}")
                            job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                            break
                        elif "gifs" in node_output:
                            video_info = node_output["gifs"][0]
                            job_results[job_id] = {
                                "filename": video_info.get("filename"),
                                "subfolder": video_info.get("subfolder", ""),
                                "type": video_info.get("type", "output")
                            }
                            print(f"[DEBUG-FALLBACK] Found gif: {job_results[job_id]}")
                            job_logs[job_id].append({"message": f"Video saved: {video_info.get('filename')}", "type": "progress"})
                            break
                        elif "images" in node_output:
                            for img in node_output["images"]:
                                if img.get("filename", "").endswith(('.mp4', '.webm', '.gif')):
                                    job_results[job_id] = {
                                        "filename": img.get("filename"),
                                        "subfolder": img.get("subfolder", ""),
                                        "type": img.get("type", "output")
                                    }
                                    print(f"[DEBUG-FALLBACK] Found video in images: {job_results[job_id]}")
                                    job_logs[job_id].append({"message": f"Video saved: {img.get('filename')}", "type": "progress"})
                                    break
                    return


def run_async(coro):
    """Run async function in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        # Get uploaded image
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        image_file = request.files['image']
        prompt = request.form.get('prompt', 'A cinematic video')
        
        # Generate job ID
        job_id = str(uuid.uuid4())[:8]
        job_logs[job_id] = []
        job_status[job_id] = "processing"
        
        # Upload image to ComfyUI
        image_data = image_file.read()
        image_filename = f"i2v_input_{job_id}.png"
        
        upload_result = run_async(upload_image_to_comfyui(image_data, image_filename))
        job_logs[job_id].append({"message": f"Image uploaded: {image_filename}", "type": "info"})
        
        # Load and configure workflow
        workflow = load_i2v_workflow()
        workflow = update_workflow_for_job(workflow, image_filename, prompt)
        job_logs[job_id].append({"message": "Workflow configured", "type": "info"})
        
        # Submit to ComfyUI
        result = run_async(submit_workflow(workflow))
        prompt_id = result.get("prompt_id")
        job_logs[job_id].append({"message": f"Workflow submitted to ComfyUI", "type": "info"})
        
        # Start WebSocket listener in background
        def listen_async():
            run_async(listen_to_websocket(prompt_id, job_id))
        
        thread = threading.Thread(target=listen_async, daemon=True)
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "prompt_id": prompt_id,
            "status": "processing"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status/<job_id>')
def status(job_id):
    if job_id not in job_logs:
        return jsonify({"error": "Job not found"}), 404
    
    # Get new logs since last check
    logs = job_logs.get(job_id, [])
    current_status = job_status.get(job_id, "processing")
    
    # Clear logs after sending (to avoid duplicates)
    response_logs = logs.copy()
    job_logs[job_id] = []
    
    return jsonify({
        "status": current_status,
        "logs": response_logs,
        "result": job_results.get(job_id)
    })


@app.route('/api/video/<job_id>')
def get_video(job_id):
    if job_id not in job_results:
        return jsonify({"error": "Video not found - job results not available"}), 404
    
    result = job_results[job_id]
    filename = result.get("filename")
    subfolder = result.get("subfolder", "")
    file_type = result.get("type", "output")
    
    if not filename:
        return jsonify({"error": "No filename in job results"}), 404
    
    # Determine mime type based on extension
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".mp4":
        mimetype = "video/mp4"
    elif ext == ".webm":
        mimetype = "video/webm"
    elif ext == ".gif":
        mimetype = "image/gif"
    else:
        mimetype = "video/mp4"
    
    # Always try fetching from ComfyUI API first (most reliable)
    try:
        url = f"{COMFYUI_URL}/view"
        params = {"filename": filename, "type": file_type}
        if subfolder:
            params["subfolder"] = subfolder
        
        print(f"Fetching video from ComfyUI: {url} params={params}")
        response = httpx.get(url, params=params, timeout=60)
        print(f"ComfyUI response: {response.status_code}, content-length: {len(response.content)}")
        
        if response.status_code == 200 and len(response.content) > 0:
            download = request.args.get('download')
            if download:
                return send_file(
                    io.BytesIO(response.content),
                    mimetype=mimetype,
                    as_attachment=True,
                    download_name=filename
                )
            return send_file(
                io.BytesIO(response.content),
                mimetype=mimetype
            )
        else:
            print(f"ComfyUI returned empty or error: status={response.status_code}")
    except Exception as e:
        print(f"Error fetching from ComfyUI: {e}")
    
    return jsonify({"error": f"Video file not found: {filename}, subfolder: {subfolder}, type: {file_type}"}), 404


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("LTXV Image-to-Video Test Server")
    print("=" * 50)
    print(f"\nComfyUI URL: {COMFYUI_URL}")
    print(f"Workflow: {os.path.join(WORKFLOW_DIR, 'ltx2_i2v.json')}")
    print(f"\nOpen http://localhost:5050 in your browser")
    print("=" * 50 + "\n")
    
    app.run(host='0.0.0.0', port=5050, debug=True)
