#!/usr/bin/env python3
"""
Downloads API Server for ComfyUI Bridge
Provides HTTP API + SSE streaming for model downloads, separate from GPU info.
"""

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# In-memory registry of active download subprocesses by model id
active_downloads = {}  # { model_id: subprocess.Popen }
active_downloads_lock = threading.Lock()


def _get_active_download(model_id: str):
    with active_downloads_lock:
        return active_downloads.get(model_id)


def _set_active_download(model_id: str, process: subprocess.Popen | None):
    with active_downloads_lock:
        if process is None:
            active_downloads.pop(model_id, None)
        else:
            active_downloads[model_id] = process

DEFAULT_MODELS_DIR = "/app/ComfyUI/models"
STABLE_DIFFUSION_CATALOG = "/app/grid-image-model-reference/stable_diffusion.json"
SIMPLE_CONFIG_PATH = "/app/comfy-bridge/model_configs.json"
LOCK_PATH = "/app/comfy-bridge/.cache/downloads.lock.json"


def _load_json_if_exists(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Known file patterns for complex models
MODEL_FILE_PATTERNS: dict[str, list[str]] = {
    "wan2.2-t2v-a14b": [
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.2_vae.safetensors",
        "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
        "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
        "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
        "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
    ],
    "wan2.2-t2v-a14b-hq": [
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.2_vae.safetensors",
        "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
        "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
    ],
    "wan2.2_ti2v_5B": [
        "wan2.2_ti2v_5B_fp16.safetensors",
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.2_vae.safetensors",
    ],
}

def _expected_files_for_model(model_id: str) -> list[str]:
    """Resolve expected filenames for a model from catalogs (best-effort)."""
    # Check known patterns first
    if model_id in MODEL_FILE_PATTERNS:
        return MODEL_FILE_PATTERNS[model_id]
    if model_id.lower() in MODEL_FILE_PATTERNS:
        return MODEL_FILE_PATTERNS[model_id.lower()]
    
    sd = _load_json_if_exists(STABLE_DIFFUSION_CATALOG)
    cfg = _load_json_if_exists(SIMPLE_CONFIG_PATH)
    files: list[str] = []
    info = None
    if isinstance(sd, dict):
        info = sd.get(model_id)
    if not info and isinstance(cfg, dict):
        info = cfg.get(model_id)
    if not isinstance(info, dict):
        return files

    def _extract_files(source: dict | list | None):
        if isinstance(source, list):
            for entry in source:
                if isinstance(entry, dict):
                    fn = entry.get("path")
                    if isinstance(fn, str) and fn:
                        files.append(fn)
                elif isinstance(entry, str) and entry:
                    files.append(entry)
            return
        if isinstance(source, dict):
            for entry in source.get("files", []) or []:
                if isinstance(entry, dict):
                    fn = entry.get("path")
                    if isinstance(fn, str) and fn:
                        files.append(fn)
                elif isinstance(entry, str) and entry:
                    files.append(entry)

    # Primary location (most entries)
    _extract_files(info.get("files"))

    # Some entries embed metadata under config
    config = info.get("config")
    if isinstance(config, dict):
        _extract_files(config.get("files"))

    if not files:
        fn = None
        if isinstance(config, dict):
            fn = config.get("file_name") or config.get("filename")
        fn = fn or info.get("file_name") or info.get("filename")
        if isinstance(fn, str) and fn:
            files.append(fn)

    # Deduplicate while preserving order
    unique_files: list[str] = []
    seen: set[str] = set()
    for fn in files:
        if fn and fn not in seen:
            unique_files.append(fn)
            seen.add(fn)

    return unique_files


def _all_files_present(model_id: str, models_dir: str) -> bool:
    expected = _expected_files_for_model(model_id)
    if not expected:
        return False
    base = Path(models_dir or DEFAULT_MODELS_DIR)
    for fn in expected:
        found = any(
            (base / sub / fn).exists()
            for sub in [
                "checkpoints",
                "vae",
                "loras",
                "text_encoders",
                "diffusion_models",
                "unet",
                "clip",
            ]
        )
        if not found:
            return False
    return True

def _read_locks() -> dict:
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_locks(data: dict) -> None:
    Path(LOCK_PATH).parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCK_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, LOCK_PATH)

def _register_lock(model_id: str, pid: int):
    locks = _read_locks()
    locks[model_id] = {"pid": pid, "timestamp": time.time()}
    _write_locks(locks)

def _remove_lock(model_id: str):
    locks = _read_locks()
    if model_id in locks:
        del locks[model_id]
        _write_locks(locks)
    else:
        # no-op if missing
        pass

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


class DownloadsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            print("[DLAPI] /health", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "timestamp": time.time()}).encode())
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/downloads":
            print("[DLAPI] POST /downloads", flush=True)
            return self.handle_downloads()
        if self.path == "/downloads/cancel":
            print("[DLAPI] POST /downloads/cancel", flush=True)
            return self.handle_cancel()
        self.send_error(404, "Not Found")

    def handle_downloads(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8"))
            models = payload.get("models") or []
            if not models:
                self.send_error(400, "No models specified")
                return

            models_dir = os.environ.get("MODELS_PATH", DEFAULT_MODELS_DIR)
            current_model = models[0]

            # Already installed? Emit immediate completion so UI clears queued state.
            if _all_files_present(current_model, models_dir):
                self._begin_sse()
                self._sse({"type": "start", "message": f"Already installed: {current_model}", "model": current_model})
                self._sse({"type": "complete", "success": True, "message": "Already installed", "models": models, "timestamp": time.time()})
                return

            # Duplicate protection - check active downloads
            existing = _get_active_download(current_model)
            if existing and existing.poll() is None:
                self._begin_sse()
                self._sse({"type": "info", "message": f"Download already in progress for {current_model}", "model": current_model})
                return
            
            # Clean up finished process if any
            if existing:
                _set_active_download(current_model, None)
            
            # Check lock file for orphaned process
            locks = _read_locks()
            lock = locks.get(current_model)
            if lock:
                pid = int(lock.get("pid", -1))
                if pid > 0 and _pid_alive(pid):
                    self._begin_sse()
                    self._sse({"type": "info", "message": f"Download already in progress for {current_model}", "model": current_model})
                    return
                else:
                    # Clean stale lock
                    print(f"[DLAPI] Cleaning stale lock for {current_model} (pid={pid})", flush=True)
                    _remove_lock(current_model)

            # Spawn download process using blockchain-based download script
            cmd = [
                "python3",
                "/app/comfy-bridge/download_models_from_chain.py",
                "--models-path",
                models_dir,
                "--models",
            ] + models

            print(f"[DLAPI] Spawning download: {' '.join(cmd)}", flush=True)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            _set_active_download(current_model, process)
            _register_lock(current_model, process.pid)
            print(f"[DLAPI] Spawned PID {process.pid} for {current_model}", flush=True)

            # Start SSE
            self._begin_sse()
            self._sse({"type": "process_info", "pid": process.pid, "model": current_model})

            import re

            last_emit = time.time()
            while True:
                line = process.stdout.readline()
                now = time.time()
                if line == "" and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    if not line:
                        continue
                    # Mirror to server log for debugging
                    print(f"[DLAPI] {line}", flush=True)
                    
                    # Check if line is SSE JSON format from emit_progress()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])  # Strip "data: " prefix
                            # Forward the JSON data directly
                            self._sse(data)
                            last_emit = now
                            continue
                        except json.JSONDecodeError:
                            pass  # Fall through to legacy parsing
                    
                    # Legacy parsing for non-JSON output
                    message_type = "info"
                    progress = 0
                    speed = ""
                    eta = ""
                    if "[PROGRESS]" in line:
                        message_type = "progress"
                        m = re.search(r"(\d+\.?\d*)\s*%", line)
                        if m:
                            progress = float(m.group(1))
                        ms = re.search(r"@\s*(\d+\.?\d*)\s*MB/s", line)
                        if ms:
                            speed = f"{ms.group(1)} MB/s"
                        me = re.search(r"ETA:\s*([^\s]+)", line)
                        if me:
                            eta = me.group(1)
                    elif "[START]" in line:
                        message_type = "start"
                    elif "[OK]" in line:
                        message_type = "success"
                    elif "[ERROR]" in line:
                        message_type = "error"
                    self._sse(
                        {
                            "type": message_type,
                            "progress": progress,
                            "speed": speed,
                            "eta": eta,
                            "message": line,
                            "model": current_model,
                            "timestamp": now,
                        }
                    )
                    last_emit = now
                else:
                    # Heartbeat every 2s
                    if now - last_emit >= 2:
                        self._sse({"type": "heartbeat", "timestamp": now})
                        last_emit = now

            rc = process.wait()
            _set_active_download(current_model, None)
            _remove_lock(current_model)
            self._sse(
                {
                    "type": "complete",
                    "success": rc == 0,
                    "message": "Download completed" if rc == 0 else "Download failed",
                    "models": models,
                    "timestamp": time.time(),
                }
            )
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Download error", "error": str(e)}).encode())

    def handle_cancel(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8"))
            model_id = payload.get("model_id")
            if not model_id:
                self.send_error(400, "model_id required")
                return
            process = _get_active_download(model_id)
            if process:
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                except Exception:
                    pass
                finally:
                    _set_active_download(model_id, None)
                    _remove_lock(model_id)
                    self._json({"success": True, "message": f"Download cancelled for {model_id}"})
                    return
            # If not found in registry, try lock PID
            lock = _read_locks().get(model_id)
            if lock:
                pid = int(lock.get("pid", -1))
                if pid > 0 and _pid_alive(pid):
                    try:
                        os.kill(pid, 15)  # SIGTERM
                        time.sleep(1)
                        if _pid_alive(pid):
                            os.kill(pid, 9)  # SIGKILL
                    except Exception:
                        pass
                _remove_lock(model_id)
                self._json({"success": True, "message": f"Cancelled stale process for {model_id}"})
                return
            # Nothing running; return success so UI clears state
            self._json({"success": True, "message": f"No active download; state cleared for {model_id}"})
        except Exception as e:
            self._json({"success": False, "message": str(e)}, 500)

    # Helpers
    def _begin_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _sse(self, obj: dict):
        try:
            self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def _json(self, obj: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())


def run_server(port: int = 8002):
    server = ThreadingHTTPServer(("", port), DownloadsHandler)
    print(f"Downloads API server running on port {port}")
    print("Endpoints:")
    print("  POST /downloads          - Start download (SSE)")
    print("  POST /downloads/cancel   - Cancel download")
    print("  GET  /health             - Health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Downloads API server...")
        server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Downloads API Server")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    run_server(args.port)


