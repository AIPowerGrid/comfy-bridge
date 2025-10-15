#!/usr/bin/env python3
"""
GPU Info API Server for ComfyUI Bridge
Provides HTTP API for GPU information
"""

import json
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

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
