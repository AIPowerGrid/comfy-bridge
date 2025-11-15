#!/usr/bin/env python3
"""
GPU Info API Server for ComfyUI Bridge
Provides HTTP API for GPU information
"""

import json
import subprocess
import os
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time
from pathlib import Path

# Global dictionary to track active download processes
active_downloads = {}  # {model_name: process}

# Paths used for resolving model files and catalogs
DEFAULT_MODELS_DIR = "/app/ComfyUI/models"
STABLE_DIFFUSION_CATALOG = "/app/grid-image-model-reference/stable_diffusion.json"
SIMPLE_CONFIG_PATH = "/app/comfy-bridge/model_configs.json"

def _load_json_if_exists(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _expected_files_for_model(model_id: str) -> list:
    """Resolve expected filenames for a model from catalogs (best-effort)."""
    sd = _load_json_if_exists(STABLE_DIFFUSION_CATALOG)
    cfg = _load_json_if_exists(SIMPLE_CONFIG_PATH)
    files = []
    info = None
    if isinstance(sd, dict):
        info = sd.get(model_id)
    if not info and isinstance(cfg, dict):
        info = cfg.get(model_id)
    if not isinstance(info, dict):
        return files

    conf = info.get("config", {}) if isinstance(info.get("config", {}), dict) else {}
    for fe in conf.get("files", []) or []:
        fn = (fe or {}).get("path")
        if isinstance(fn, str) and fn:
            files.append(fn)

    if not files:
        fn = conf.get("file_name") or info.get("filename")
        if isinstance(fn, str) and fn:
            files.append(fn)
    return files

def _all_files_present(model_id: str, models_dir: str) -> bool:
    expected = _expected_files_for_model(model_id)
    if not expected:
        return False
    base = Path(models_dir or DEFAULT_MODELS_DIR)
    for fn in expected:
        found = any((base / sub / fn).exists() for sub in ["checkpoints","vae","loras","text_encoders","diffusion_models","unet","clip"])
        if not found:
            return False
    return True

def periodic_catalog_sync():
    """Run catalog sync every 60 seconds"""
    while True:
        try:
            print("Running periodic catalog sync...")
            from catalog_sync import sync_catalog
            success = sync_catalog()
            if success:
                print("Periodic catalog sync completed successfully")
            else:
                print("Periodic catalog sync failed")
        except Exception as e:
            print(f"Error in periodic catalog sync: {e}")
        
        # Wait 60 seconds before next sync
        time.sleep(60)

class GPUInfoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/gpu-info':
            self.handle_gpu_info()
        elif parsed_path.path == '/health':
            self.handle_health()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/sync-catalog':
            self.handle_sync_catalog()
        elif parsed_path.path == '/api/download-models':
            self.handle_download_models()
        elif parsed_path.path == '/api/cancel-download':
            self.handle_cancel_download()
        else:
            self.send_error(404, "Not Found")
    
    def handle_gpu_info(self):
        """Handle GPU info requests"""
        try:
            # Import the GPU info function
            from get_gpu_info import get_nvidia_gpu_info, get_cpu_info
            
            # Try NVIDIA first
            gpu_info = get_nvidia_gpu_info()
            
            # Fallback to CPU if no GPU available
            if not gpu_info['available']:
                gpu_info = get_cpu_info()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(gpu_info).encode())
            
        except Exception as e:
            self.send_error(500, f"GPU info error: {str(e)}")
    
    def handle_health(self):
        """Handle health check requests"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        health_data = {
            'status': 'healthy',
            'timestamp': time.time()
        }
        
        self.wfile.write(json.dumps(health_data).encode())
    
    def handle_sync_catalog(self):
        """Handle catalog sync requests"""
        try:
            # Import the catalog sync function
            from catalog_sync import sync_catalog
            
            # Run the sync
            success = sync_catalog()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            result = {
                'success': success,
                'message': 'Catalog sync completed' if success else 'Catalog sync failed',
                'output': 'Sync completed successfully' if success else 'Sync failed',
                'error': None if success else 'Sync failed'
            }
            
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            result = {
                'success': False,
                'message': 'Catalog sync error',
                'output': '',
                'error': str(e)
            }
            
            self.wfile.write(json.dumps(result).encode())
    
    def handle_download_models(self):
        """Handle model download requests"""
        try:
            # Get the request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            models = request_data.get('models', [])
            if not models:
                self.send_error(400, "No models specified")
                return
            
            # Import the download function
            import subprocess
            import sys
            
            # Determine models dir
            models_dir = os.environ.get("MODELS_PATH", DEFAULT_MODELS_DIR)
            
            # Short-circuit if files already present to avoid UI 'queued' loop
            current_model = models[0] if models else None
            if current_model and _all_files_present(current_model, models_dir):
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(f"data: {json.dumps({'type':'start','message':f'Already installed: {current_model}','model':current_model})}\n\n".encode())
                self.wfile.write(f"data: {json.dumps({'type':'complete','success':True,'message':'Already installed','models':models,'timestamp':time.time()})}\n\n".encode())
                self.wfile.flush()
                return
            
            # Prevent duplicate concurrent downloads
            if current_model and current_model in active_downloads and active_downloads[current_model].poll() is None:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(f"data: {json.dumps({'type':'info','message':f'Download already in progress for {current_model}','model':current_model})}\n\n".encode())
                self.wfile.flush()
                return
            
            # Run the download script
            # Pass models as separate arguments (the script uses nargs='+')
            cmd = [
                'python3', '/app/comfy-bridge/download_models_from_catalog.py',
                '--models-path', models_dir,
                '--config', '/app/comfy-bridge/model_configs.json',
                '--models'
            ] + models
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Store process globally for cancellation
            current_model = models[0] if models else None
            if current_model:
                active_downloads[current_model] = process
            
            # Set up streaming response
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Send PID immediately so client can track it
            pid_data = {
                'type': 'process_info',
                'pid': process.pid,
                'model': current_model
            }
            self.wfile.write(f"data: {json.dumps(pid_data)}\n\n".encode())
            self.wfile.flush()
            
            # Stream output line by line
            import re
            last_emit = time.time()
            
            while True:
                output = process.stdout.readline()
                now = time.time()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_line = output.strip()
                    if not output_line:
                        continue
                    
                    # Parse different message types
                    progress = 0
                    speed = ''
                    eta = ''
                    message_type = 'info'
                    
                    # Check for progress updates: [PROGRESS] 45.2% (2.1/4.7 MB) @ 15.3 MB/s ETA: 2m30s
                    if '[PROGRESS]' in output_line:
                        message_type = 'progress'
                        progress_match = re.search(r'(\d+\.?\d*)\s*%', output_line)
                        if progress_match:
                            progress = float(progress_match.group(1))
                        
                        speed_match = re.search(r'@\s*(\d+\.?\d*)\s*MB/s', output_line)
                        if speed_match:
                            speed = f"{speed_match.group(1)} MB/s"
                        
                        eta_match = re.search(r'ETA:\s*([^\s]+)', output_line)
                        if eta_match:
                            eta = eta_match.group(1)
                    
                    # Check for model start: [START] Downloading model: model_name
                    elif '[START]' in output_line:
                        message_type = 'start'
                        model_match = re.search(r'Downloading model:\s*(.+)', output_line)
                        if model_match:
                            current_model = model_match.group(1).strip()
                    
                    # Check for success: [OK] ...
                    elif '[OK]' in output_line:
                        message_type = 'success'
                    
                    # Check for errors: [ERROR] ...
                    elif '[ERROR]' in output_line:
                        message_type = 'error'
                    
                    # Send progress update
                    progress_data = {
                        'type': message_type,
                        'progress': progress,
                        'speed': speed,
                        'eta': eta,
                        'message': output_line,
                        'model': current_model,
                        'timestamp': time.time()
                    }
                    
                    try:
                        self.wfile.write(f"data: {json.dumps(progress_data)}\n\n".encode())
                        self.wfile.flush()
                        last_emit = now
                    except BrokenPipeError:
                        # Client disconnected, stop streaming
                        break
                else:
                    # Heartbeat every 2 seconds to keep UI connection alive
                    if now - last_emit >= 2:
                        try:
                            self.wfile.write(b"data: {\"type\": \"heartbeat\"}\n\n")
                            self.wfile.flush()
                            last_emit = now
                        except BrokenPipeError:
                            break
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Clean up from active downloads
            if current_model and current_model in active_downloads:
                del active_downloads[current_model]
            
            # Send completion message
            result_data = {
                'type': 'complete',
                'success': return_code == 0,
                'message': f"Download {'completed' if return_code == 0 else 'failed'}",
                'models': models,
                'timestamp': time.time()
            }
            try:
                self.wfile.write(f"data: {json.dumps(result_data)}\n\n".encode())
            except BrokenPipeError:
                # Client disconnected, but download completed successfully
                pass
            
        except Exception as e:
            # Clean up from active downloads on error
            if 'current_model' in locals() and current_model and current_model in active_downloads:
                del active_downloads[current_model]
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            result = {
                'success': False,
                'message': 'Download error',
                'error': str(e)
            }
            
            self.wfile.write(json.dumps(result).encode())
    
    def handle_cancel_download(self):
        """Handle download cancellation requests"""
        try:
            # Get the request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            model_id = request_data.get('model_id')
            if not model_id:
                self.send_error(400, "No model_id specified")
                return
            
            # Check if download is active
            if model_id not in active_downloads:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                result = {
                    'success': False,
                    'message': f'No active download for model: {model_id}'
                }
                self.wfile.write(json.dumps(result).encode())
                return
            
            # Kill the process
            process = active_downloads[model_id]
            try:
                # Try graceful termination first
                process.terminate()
                # Wait up to 3 seconds for graceful shutdown
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    process.kill()
                    process.wait()
                
                # Clean up
                del active_downloads[model_id]
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                result = {
                    'success': True,
                    'message': f'Download cancelled for model: {model_id}'
                }
                self.wfile.write(json.dumps(result).encode())
                
            except Exception as kill_error:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                result = {
                    'success': False,
                    'message': f'Failed to cancel download: {str(kill_error)}'
                }
                self.wfile.write(json.dumps(result).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            result = {
                'success': False,
                'message': 'Cancel request error',
                'error': str(e)
            }
            self.wfile.write(json.dumps(result).encode())
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

def run_server(port=8001):
    """Run the GPU info API server"""
    # Start periodic catalog sync in background thread
    sync_thread = threading.Thread(target=periodic_catalog_sync, daemon=True)
    sync_thread.start()
    print("Started periodic catalog sync thread (every 60 seconds)")
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, GPUInfoHandler)
    
    print(f"GPU Info API server running on port {port}")
    print(f"Endpoints:")
    print(f"  GET /gpu-info - Get GPU information")
    print(f"  GET /health - Health check")
    print(f"  POST /api/sync-catalog - Sync model catalog")
    print(f"  POST /api/download-models - Download models")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down GPU Info API server...")
        httpd.shutdown()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='GPU Info API Server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run server on')
    
    args = parser.parse_args()
    
    run_server(args.port)
