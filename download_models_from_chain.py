#!/usr/bin/env python3
"""
Blockchain-Based Model Download Script for ComfyUI Bridge
Downloads models using ONLY the blockchain as the source of truth.
No JSON catalogs are used - all model info comes from the chain.
"""

import os
import sys
import time
import json
import struct
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Global model name for progress tracking
_current_model = ""

def emit_progress(progress: float, speed: str = "", eta: str = "", message: str = "", msg_type: str = "info"):
    """Emit a JSON progress message for the management UI."""
    data = {
        "type": msg_type,
        "progress": round(progress, 1),
        "speed": speed,
        "eta": eta,
        "message": message,
        "model": _current_model,
        "timestamp": time.time()
    }
    print(f"data: {json.dumps(data)}", flush=True)
    print(flush=True)  # Empty line for SSE format

# Load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in the script's directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] Loaded environment from {env_path}")
except ImportError:
    # python-dotenv not installed, try manual loading
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

# Import blockchain client
from comfy_bridge.modelvault_client import (
    get_modelvault_client,
    OnChainModelInfo,
    ModelFile,
    ModelType,
)

# Import fallback catalog
try:
    from model_catalog import get_catalog_model, CatalogModel
    CATALOG_AVAILABLE = True
except ImportError:
    CATALOG_AVAILABLE = False
    print("[INFO] Fallback model catalog not available")


def normalize_model_folder(file_type: str) -> str:
    """Normalize file type to ComfyUI folder name."""
    n = file_type.strip().lower()
    if n in ('ckpt', 'checkpoint', 'checkpoints'):
        return 'checkpoints'
    if n in ('vae', 'vaes'):
        return 'vae'
    if n in ('lora', 'loras'):
        return 'loras'
    if n in ('text_encoder', 'text_encoders', 'clip'):
        return 'text_encoders'
    if n in ('diffusion_models', 'diffusion', 'unet'):
        return 'diffusion_models'
    return n or 'checkpoints'


def _expected_safetensors_size(filepath: Path) -> Tuple[bool, Optional[int]]:
    """
    Parse the safetensors header to ensure the payload is fully present.
    Returns (is_valid, required_size_bytes or None).
    """
    try:
        with open(filepath, "rb") as f:
            header_size_raw = f.read(8)
            if len(header_size_raw) != 8:
                return False, None
            header_size = struct.unpack("<Q", header_size_raw)[0]
            header_bytes = f.read(header_size)
            if len(header_bytes) != header_size:
                return False, None
            import json
            header = json.loads(header_bytes)
        max_offset = 0
        for tensor_meta in header.values():
            if isinstance(tensor_meta, dict):
                offsets = tensor_meta.get("data_offsets")
                if isinstance(offsets, list) and len(offsets) == 2:
                    max_offset = max(max_offset, int(offsets[1]))
        required_size = 8 + header_size + max_offset
        actual_size = filepath.stat().st_size
        if max_offset == 0:
            return True, required_size
        return actual_size >= required_size, required_size
    except Exception as exc:
        print(f"[WARN] Failed to inspect safetensors header for {filepath}: {exc}")
        return False, None


def _is_file_complete(filepath: Path) -> bool:
    """Check if a downloaded file is complete."""
    if not filepath.exists():
        return False
    if filepath.suffix == ".safetensors":
        ok, required_size = _expected_safetensors_size(filepath)
        if not ok:
            req = f" (expected ≥ {required_size} bytes)" if required_size else ""
            print(f"[WARN] Detected incomplete safetensors file: {filepath}{req}")
            return False
    return True


def download_file(
    url: str, 
    filepath: Path, 
    expected_hash: Optional[str] = None,
    progress_callback=None
) -> Tuple[bool, Optional[str]]:
    """
    Download a file from URL with progress reporting.
    Returns: (success, error_message)
    """
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Add API keys for authenticated downloads
        if 'huggingface.co' in url:
            hf_token = os.environ.get('HUGGING_FACE_API_KEY') or os.environ.get('HF_TOKEN')
            if hf_token:
                request_headers['Authorization'] = f"Bearer {hf_token}"
        
        if 'civitai.com' in url:
            civitai_key = os.environ.get('CIVITAI_API_KEY')
            if civitai_key:
                # CivitAI uses token as query parameter
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}token={civitai_key}"
        
        response = requests.get(url, headers=request_headers, stream=True, timeout=300, allow_redirects=True)
        response.raise_for_status()
        
        # Check content type - if HTML, it's likely an error page
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type:
            return False, "Received HTML instead of file - check if API key is required (set CIVITAI_API_KEY for CivitAI)"
        
        total_size = int(response.headers.get('content-length', 0))
        
        # Sanity check - model files should be at least 1MB
        if total_size > 0 and total_size < 1_000_000:
            return False, f"File too small ({total_size} bytes) - likely an error response. Set CIVITAI_API_KEY for CivitAI downloads"
        downloaded = 0
        start_time = time.time()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        progress_callback(progress, downloaded, total_size, speed, eta)
        
        if total_size > 0 and downloaded != total_size:
            print(f"[ERROR] Download incomplete: expected {total_size} bytes, got {downloaded}")
            filepath.unlink(missing_ok=True)
            return False, "Incomplete download"
        
        # Verify hash if provided
        if expected_hash and len(expected_hash) == 64:
            print(f"[VERIFY] Checking SHA256 hash...")
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(32 * 1024 * 1024), b''):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().upper()
            if actual_hash != expected_hash.upper():
                print(f"[ERROR] Hash mismatch! Expected: {expected_hash}, Got: {actual_hash}")
                filepath.unlink(missing_ok=True)
                return False, "Hash verification failed"
        
        size_mb = downloaded / (1024 * 1024)
        elapsed = time.time() - start_time
        speed_mb = size_mb / elapsed if elapsed > 0 else 0
        print(f"[OK] Downloaded {filepath.name} ({size_mb:.2f} MB in {elapsed:.1f}s @ {speed_mb:.2f} MB/s)")
        
        return True, None
        
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.RequestException as e:
        return False, f"Download error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def download_model_from_chain(
    model_info: OnChainModelInfo,
    models_path: str,
    downloaded: set = None
) -> bool:
    """
    Download a single model using info from blockchain.
    Returns True if successful.
    """
    global _current_model
    _current_model = model_info.display_name
    
    if downloaded is None:
        downloaded = set()
    
    if model_info.display_name in downloaded:
        emit_progress(100, message=f"[SKIP] {model_info.display_name} already processed")
        return True
    
    emit_progress(0, message=f"[MODEL] {model_info.display_name}")
    emit_progress(0, message=f"  Type: {model_info.model_type.name}")
    emit_progress(0, message=f"  Base: {model_info.base_model}")
    
    # Check if model has download files
    if not model_info.files:
        emit_progress(0, message=f"[WARN] No download files registered for {model_info.display_name}", msg_type="warning")
        emit_progress(0, message=f"  This model needs to be registered with download URLs (V2 contract)", msg_type="warning")
        return False
    
    success_count = 0
    total_files = len(model_info.files)
    
    for idx, file_info in enumerate(model_info.files, 1):
        folder = normalize_model_folder(file_info.file_type)
        filepath = Path(models_path) / folder / file_info.file_name
        
        # Calculate base progress for this file
        file_base_progress = ((idx - 1) / total_files) * 100
        file_progress_range = 100 / total_files
        
        emit_progress(file_base_progress, message=f"[FILE] [{idx}/{total_files}] {file_info.file_name} -> {folder}/")
        
        # Check if already exists
        if filepath.exists() and _is_file_complete(filepath):
            emit_progress(file_base_progress + file_progress_range, message=f"  ✓ Already downloaded: {file_info.file_name}")
            success_count += 1
            continue
        
        # Remove incomplete file
        if filepath.exists():
            emit_progress(file_base_progress, message=f"  Removing incomplete file...")
            filepath.unlink()
        
        # Download with progress output
        last_emit_time = [0]  # Use list to allow modification in nested function
        
        def progress_cb(pct, dl, total, speed, eta):
            # Throttle progress updates to every 0.5 seconds
            now = time.time()
            if now - last_emit_time[0] < 0.5 and pct < 99:
                return
            last_emit_time[0] = now
            
            speed_mb = speed / (1024 * 1024)
            speed_str = f"{speed_mb:.1f} MB/s"
            eta_str = f"{eta:.0f}s" if eta < 60 else f"{eta/60:.1f}m"
            
            # Calculate overall progress including file position
            overall_pct = file_base_progress + (pct / 100) * file_progress_range
            
            message = f"  [{pct:.1f}%] {file_info.file_name}: {dl/(1024*1024):.1f}/{total/(1024*1024):.1f} MB"
            emit_progress(overall_pct, speed=speed_str, eta=eta_str, message=message)
        
        # Try primary URL
        url_preview = file_info.download_url[:80] + "..." if len(file_info.download_url) > 80 else file_info.download_url
        emit_progress(file_base_progress, message=f"  Downloading: {url_preview}")
        success, error = download_file(
            file_info.download_url,
            filepath,
            file_info.sha256_hash,
            progress_cb
        )
        
        # Try mirror if primary fails
        if not success and file_info.mirror_url:
            emit_progress(file_base_progress, message=f"  Primary failed, trying mirror...")
            success, error = download_file(
                file_info.mirror_url,
                filepath,
                file_info.sha256_hash,
                progress_cb
            )
        
        if success:
            success_count += 1
            emit_progress(file_base_progress + file_progress_range, message=f"  ✓ Downloaded: {file_info.file_name}")
        else:
            emit_progress(file_base_progress, message=f"  [ERROR] {error}", msg_type="error")
    
    downloaded.add(model_info.display_name)
    final_success = success_count == total_files
    
    if final_success:
        emit_progress(100, message=f"[SUCCESS] {model_info.display_name} - {success_count}/{total_files} files")
    else:
        emit_progress(100, message=f"[PARTIAL] {model_info.display_name} - {success_count}/{total_files} files", msg_type="warning")
    
    return final_success


def download_model_from_catalog(
    catalog_model: 'CatalogModel',
    models_path: str,
    downloaded: set = None
) -> bool:
    """
    Download a model from the fallback catalog.
    Returns True if successful.
    """
    global _current_model
    _current_model = catalog_model.name
    
    if downloaded is None:
        downloaded = set()
    
    if catalog_model.name in downloaded:
        emit_progress(100, message=f"[SKIP] {catalog_model.name} already processed")
        return True
    
    emit_progress(0, message=f"[CATALOG] {catalog_model.name}")
    emit_progress(0, message=f"  Description: {catalog_model.description}")
    emit_progress(0, message=f"  Base: {catalog_model.base_model}")
    emit_progress(0, message=f"  Files: {len(catalog_model.files)}")
    
    success_count = 0
    total_files = len(catalog_model.files)
    
    for idx, file_info in enumerate(catalog_model.files, 1):
        file_name = file_info.file_name
        
        # Check if already downloaded
        if file_name in downloaded:
            emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - already downloaded")
            success_count += 1
            continue
        
        # Determine target directory
        target_dir = Path(models_path) / file_info.target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name
        
        # Check if file already exists
        if target_path.exists():
            if file_info.size_bytes > 0:
                actual_size = target_path.stat().st_size
                if actual_size >= file_info.size_bytes * 0.95:  # 5% tolerance
                    emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - already exists ({actual_size / 1e9:.1f}GB)")
                    downloaded.add(file_name)
                    success_count += 1
                    continue
                else:
                    emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - incomplete ({actual_size / 1e9:.1f}GB), re-downloading")
            else:
                emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - already exists")
                downloaded.add(file_name)
                success_count += 1
                continue
        
        # Download the file
        emit_progress(0, message=f"  [{idx}/{total_files}] Downloading {file_name}...")
        download_url = file_info.download_url
        
        if not download_url:
            emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - NO URL", msg_type="warning")
            continue
        
        success, error = download_file(download_url, target_path, progress_callback=emit_progress)
        
        if success:
            downloaded.add(file_name)
            success_count += 1
            emit_progress(100, message=f"  [{idx}/{total_files}] {file_name} - downloaded successfully")
        else:
            emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - FAILED: {error}", msg_type="error")
    
    downloaded.add(catalog_model.name)
    final_success = success_count == total_files
    
    if final_success:
        emit_progress(100, message=f"[OK] {catalog_model.name} - all {total_files} files")
    else:
        emit_progress(100, message=f"[PARTIAL] {catalog_model.name} - {success_count}/{total_files} files", msg_type="warning")
    
    return final_success


def download_models_from_chain(
    model_names: List[str],
    models_path: str = "/app/ComfyUI/models"
) -> bool:
    """
    Download multiple models using blockchain as source of truth.
    
    Args:
        model_names: List of model display names to download
        models_path: Path to ComfyUI models directory
        
    Returns:
        True if all models downloaded successfully
    """
    global _current_model
    _current_model = model_names[0] if model_names else ""
    
    # Emit start event
    start_data = {
        "type": "start",
        "model": _current_model,
        "message": f"Starting download for {_current_model}..."
    }
    print(f"data: {json.dumps(start_data)}", flush=True)
    print(flush=True)
    
    emit_progress(0, message="=" * 60)
    emit_progress(0, message="Blockchain Model Download")
    emit_progress(0, message="=" * 60)
    emit_progress(0, message=f"Models path: {models_path}")
    emit_progress(0, message=f"Requested: {len(model_names)} model(s)")
    emit_progress(0, message="=" * 60)
    
    # Get blockchain client
    client = get_modelvault_client()
    
    if not client.enabled:
        emit_progress(0, message="[ERROR] ModelVault client not available", msg_type="error")
        return False
    
    # Fetch all models from chain
    emit_progress(0, message="[CHAIN] Fetching models from blockchain...")
    total = client.get_total_models()
    emit_progress(0, message=f"  Total models on chain: {total}")
    
    all_models = client.fetch_all_models()
    emit_progress(0, message=f"  Loaded: {len(all_models)} models")
    
    if not all_models:
        emit_progress(0, message="[ERROR] No models found on blockchain", msg_type="error")
        emit_progress(0, message="  Please register models to the blockchain first", msg_type="error")
        return False
    
    # Resolve requested models
    models_to_download = []
    not_found = []
    
    for name in model_names:
        model = client.find_model(name)
        if model:
            models_to_download.append(model)
        else:
            not_found.append(name)
    
    # Try fallback catalog for models not found on chain
    catalog_downloads = []
    still_not_found = []
    
    if not_found and CATALOG_AVAILABLE:
        emit_progress(0, message=f"[CATALOG] Checking fallback catalog for {len(not_found)} model(s)...")
        for name in not_found:
            catalog_model = get_catalog_model(name)
            if catalog_model:
                emit_progress(0, message=f"  ✓ Found '{name}' in fallback catalog")
                catalog_downloads.append((name, catalog_model))
            else:
                still_not_found.append(name)
        
        if still_not_found:
            emit_progress(0, message=f"[WARN] Models not found anywhere: {', '.join(still_not_found)}", msg_type="warning")
    elif not_found:
        still_not_found = not_found
        emit_progress(0, message=f"[WARN] Models not found on chain: {', '.join(not_found)}", msg_type="warning")
    
    if not models_to_download and not catalog_downloads:
        emit_progress(0, message="[ERROR] No resolvable models found", msg_type="error")
        return False
    
    # Check blockchain models for missing download URLs and use catalog fallback
    if CATALOG_AVAILABLE:
        for model in list(models_to_download):
            if not model.files:
                catalog_model = get_catalog_model(model.display_name)
                if catalog_model:
                    emit_progress(0, message=f"  ✓ Using catalog files for '{model.display_name}' (no blockchain URLs)")
                    models_to_download.remove(model)
                    catalog_downloads.append((model.display_name, catalog_model))
    
    emit_progress(0, message=f"[DOWNLOAD] {len(models_to_download) + len(catalog_downloads)} model(s) to process:")
    for m in models_to_download:
        files_str = f"{len(m.files)} files" if m.files else "NO FILES"
        emit_progress(0, message=f"  • {m.display_name} ({files_str}) [blockchain]")
    for name, cm in catalog_downloads:
        emit_progress(0, message=f"  • {name} ({len(cm.files)} files) [catalog]")
    
    # Download each model from blockchain
    downloaded = set()
    success_count = 0
    total_models = len(models_to_download) + len(catalog_downloads)
    
    for model in models_to_download:
        if download_model_from_chain(model, models_path, downloaded):
            success_count += 1
    
    # Download models from fallback catalog
    for name, catalog_model in catalog_downloads:
        if download_model_from_catalog(catalog_model, models_path, downloaded):
            success_count += 1
    
    emit_progress(100, message="=" * 60)
    all_success = success_count == total_models
    if all_success:
        emit_progress(100, message=f"[COMPLETE] Downloaded: {success_count}/{len(models_to_download)} models")
    else:
        emit_progress(100, message=f"[SUMMARY] Downloaded: {success_count}/{len(models_to_download)} models", msg_type="warning")
    emit_progress(100, message="=" * 60)
    
    # Emit final complete event
    complete_data = {
        "type": "complete",
        "success": all_success,
        "message": "Download complete" if all_success else "Download partially complete",
        "models": model_names,
        "timestamp": time.time()
    }
    print(f"data: {json.dumps(complete_data)}", flush=True)
    print(flush=True)
    
    return all_success


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download models from blockchain registry'
    )
    parser.add_argument(
        '--models', 
        nargs='+', 
        help='Model names to download (if not specified, uses WORKFLOW_FILE env)'
    )
    parser.add_argument(
        '--models-path',
        default=os.environ.get('MODELS_PATH', '/app/ComfyUI/models'),
        help='Path to ComfyUI models directory'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all models registered on blockchain'
    )
    
    args = parser.parse_args()
    
    # List mode
    if args.list:
        client = get_modelvault_client()
        if not client.enabled:
            print("ModelVault client not available")
            sys.exit(1)
        
        models = client.fetch_all_models()
        print(f"\nModels on blockchain ({len(models)}):")
        for name, info in models.items():
            if name == info.display_name:  # Only show once per model
                files_str = f"{len(info.files)} files" if info.files else "no files"
                print(f"  • {info.display_name} ({info.model_type.name}, {files_str})")
        sys.exit(0)
    
    # Get models to download
    model_names = args.models
    if not model_names:
        # Try from environment
        workflow_env = os.environ.get('WORKFLOW_FILE', '')
        if workflow_env:
            model_names = [m.strip() for m in workflow_env.split(',') if m.strip()]
        else:
            grid_env = os.environ.get('GRID_MODEL', '')
            if grid_env:
                model_names = [m.strip() for m in grid_env.split(',') if m.strip()]
    
    if not model_names:
        print("No models specified. Use --models or set WORKFLOW_FILE/GRID_MODEL env var")
        sys.exit(1)
    
    # Download
    success = download_models_from_chain(model_names, args.models_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
