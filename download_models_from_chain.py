#!/usr/bin/env python3
"""
Blockchain-Based Model Download Script for ComfyUI Bridge
Downloads models using ONLY the blockchain as the source of truth.
No JSON catalogs are used - all model info comes from the chain.
"""

import os
import sys
import time
import struct
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Import blockchain client
from comfy_bridge.modelvault_client import (
    get_modelvault_client,
    OnChainModelInfo,
    ModelFile,
    ModelType,
)


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
                request_headers['Authorization'] = f"Bearer {civitai_key}"
        
        response = requests.get(url, headers=request_headers, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
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
    if downloaded is None:
        downloaded = set()
    
    if model_info.display_name in downloaded:
        print(f"[SKIP] {model_info.display_name} already processed")
        return True
    
    print(f"\n[MODEL] {model_info.display_name}")
    print(f"  Type: {model_info.model_type.name}")
    print(f"  Base: {model_info.base_model}")
    
    # Check if model has download files
    if not model_info.files:
        print(f"[WARN] No download files registered for {model_info.display_name}")
        print(f"  This model needs to be registered with download URLs (V2 contract)")
        return False
    
    success_count = 0
    total_files = len(model_info.files)
    
    for idx, file_info in enumerate(model_info.files, 1):
        folder = normalize_model_folder(file_info.file_type)
        filepath = Path(models_path) / folder / file_info.file_name
        
        print(f"[FILE] [{idx}/{total_files}] {file_info.file_name} -> {folder}/")
        
        # Check if already exists
        if filepath.exists() and _is_file_complete(filepath):
            print(f"  ✓ Already downloaded")
            success_count += 1
            continue
        
        # Remove incomplete file
        if filepath.exists():
            print(f"  Removing incomplete file...")
            filepath.unlink()
        
        # Download with filename in progress output
        def progress_cb(pct, dl, total, speed, eta):
            speed_mb = speed / (1024 * 1024)
            eta_str = f"{eta:.0f}s" if eta < 60 else f"{eta/60:.1f}m"
            # Include filename for clarity in logs
            print(f"  [{pct:.1f}%] {file_info.file_name}: {dl/(1024*1024):.1f}/{total/(1024*1024):.1f} MB @ {speed_mb:.1f} MB/s ETA: {eta_str}", end='\r')
        
        # Try primary URL
        success, error = download_file(
            file_info.download_url,
            filepath,
            file_info.sha256_hash,
            progress_cb
        )
        
        # Try mirror if primary fails
        if not success and file_info.mirror_url:
            print(f"  Primary failed, trying mirror...")
            success, error = download_file(
                file_info.mirror_url,
                filepath,
                file_info.sha256_hash,
                progress_cb
            )
        
        if success:
            success_count += 1
        else:
            print(f"  [ERROR] {error}")
    
    downloaded.add(model_info.display_name)
    return success_count == total_files


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
    print("=" * 60)
    print("Blockchain Model Download")
    print("=" * 60)
    print(f"Models path: {models_path}")
    print(f"Requested: {len(model_names)} model(s)")
    print("=" * 60)
    
    # Get blockchain client
    client = get_modelvault_client()
    
    if not client.enabled:
        print("[ERROR] ModelVault client not available")
        return False
    
    # Fetch all models from chain
    print("\n[CHAIN] Fetching models from blockchain...")
    total = client.get_total_models()
    print(f"  Total models on chain: {total}")
    
    all_models = client.fetch_all_models()
    print(f"  Loaded: {len(all_models)} models")
    
    if not all_models:
        print("[ERROR] No models found on blockchain")
        print("  Please register models to the blockchain first")
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
    
    if not_found:
        print(f"\n[WARN] Models not found on chain: {', '.join(not_found)}")
    
    if not models_to_download:
        print("[ERROR] No resolvable models found on blockchain")
        return False
    
    print(f"\n[DOWNLOAD] {len(models_to_download)} model(s) to process:")
    for m in models_to_download:
        files_str = f"{len(m.files)} files" if m.files else "NO FILES"
        print(f"  • {m.display_name} ({files_str})")
    
    # Download each model
    downloaded = set()
    success_count = 0
    
    for model in models_to_download:
        if download_model_from_chain(model, models_path, downloaded):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"[SUMMARY] Downloaded: {success_count}/{len(models_to_download)} models")
    print("=" * 60)
    
    return success_count == len(models_to_download)


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
