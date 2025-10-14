#!/usr/bin/env python3
"""Simple GPU Info API server for ComfyUI Bridge Management UI"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import sys

class GPUInfoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/gpu-info':
            try:
                # Run get_gpu_info.py to get GPU information
                result = subprocess.run(
                    [sys.executable, '/app/comfy-bridge/get_gpu_info.py'],
                    capture_output=True,
                    text=True
                )
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                # Send the GPU info
                self.wfile.write(result.stdout.encode())
                
            except Exception as e:
                # Send error response
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_data = json.dumps({'error': str(e)})
                self.wfile.write(error_data.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress normal request logging"""
        return

def main():
    port = 8001
    server_address = ('', port)
    httpd = HTTPServer(server_address, GPUInfoHandler)
    print(f"GPU Info API server listening on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    main()

