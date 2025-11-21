#!/usr/bin/env python3
"""
Model Download Script for ComfyUI Bridge
Downloads models from various sources based on catalog configuration
Supports multiple files per model (checkpoints, VAE, LoRAs, text encoders, etc.)
"""

import json
import os
import sys
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import time

def load_stable_diffusion_catalog(catalog_path: str = '/app/grid-image-model-reference/stable_diffusion.json') -> Dict[str, Any]:
    """Load stable_diffusion.json catalog"""
    try:
        with open(catalog_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {catalog_path} not found", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing {catalog_path}: {e}", file=sys.stderr)
        return {}

def load_model_configs(config_path: str = 'model_configs.json') -> Dict[str, Any]:
    """Load model_configs.json (fallback for simple format)"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing {config_path}: {e}", file=sys.stderr)
        return {}

def normalize_model_folder(name: str) -> str:
    """Normalize folder aliases to ComfyUI canonical names."""
    if not isinstance(name, str):
        return 'checkpoints'
    n = name.strip().lower()
    # Canonical mappings
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

def determine_model_folder(file_url: str, file_name: str, file_path: str = '', default_type: str = 'checkpoints') -> str:
    """
    Determine which folder to place the file in based on URL path, filename, or file_path
    Returns: folder name (checkpoints, vae, loras, text_encoders, diffusion_models, etc.)
    """
    url_lower = file_url.lower()
    name_lower = file_name.lower()
    path_lower = file_path.lower() if file_path else ''
    
    # Check URL path for folder hints (most reliable)
    if '/vae/' in url_lower:
        return 'vae'
    elif '/loras/' in url_lower or '/lora/' in url_lower:
        return 'loras'
    elif '/text_encoders/' in url_lower or '/clip/' in url_lower:
        return 'text_encoders'
    elif '/diffusion_models/' in url_lower or '/unet/' in url_lower:
        return 'diffusion_models'
    elif '/checkpoints/' in url_lower:
        return 'checkpoints'
    
    # Check file_path if provided
    if file_path:
        if '/vae/' in path_lower:
            return 'vae'
        elif '/loras/' in path_lower or '/lora/' in path_lower:
            return 'loras'
        elif '/text_encoders/' in path_lower or '/clip/' in path_lower:
            return 'text_encoders'
        elif '/diffusion_models/' in path_lower or '/unet/' in path_lower:
            return 'diffusion_models'
        elif '/checkpoints/' in path_lower:
            return 'checkpoints'
    
    # Check filename patterns
    if 'vae' in name_lower and ('vae' in name_lower.replace('encoder', '')):
        return 'vae'
    elif 'lora' in name_lower:
        return 'loras'
    elif 'text_encoder' in name_lower or 'clip' in name_lower or 'umt5' in name_lower:
        return 'text_encoders'
    elif 'diffusion' in name_lower or 'unet' in name_lower:
        return 'diffusion_models'
    
    # Default based on file extension and default_type (normalize aliases)
    if default_type and default_type.lower() != 'checkpoints':
        return normalize_model_folder(default_type)
    
    # Default to checkpoints for .ckpt and .safetensors files
    if file_name.endswith(('.ckpt', '.safetensors')):
        return 'checkpoints'
    
    return 'checkpoints'

def get_download_urls_from_model(model_info: Dict[str, Any], model_id: str) -> List[Dict[str, str]]:
    """
    Extract all download URLs from a model configuration
    Returns list of dicts with: file_url, file_name, file_type
    """
    downloads = []
    
    # Try stable_diffusion.json format first (config.download[])
    if 'config' in model_info:
        config = model_info['config']
        
        # Check for config.download[] array
        if 'download' in config and isinstance(config['download'], list):
            for download_entry in config['download']:
                if 'file_url' in download_entry and download_entry['file_url']:
                    file_name = download_entry.get('file_name') or download_entry.get('file_path') or ''
                    if not file_name:
                        # Extract from URL
                        parsed = urlparse(download_entry['file_url'])
                        file_name = os.path.basename(parsed.path).split('?')[0]
                    
                    file_type = determine_model_folder(
                        download_entry['file_url'],
                        file_name,
                        download_entry.get('file_path', ''),
                        model_info.get('type', 'checkpoints')
                    )
                    
                    downloads.append({
                        'file_url': download_entry['file_url'],
                        'file_name': file_name,
                        'file_type': file_type
                    })
        
        # Fallback to config.download_url or config.file_url
        if not downloads:
            download_url = config.get('download_url') or config.get('file_url')
            if download_url:
                file_name = config.get('file_name') or model_info.get('filename', '')
                if not file_name:
                    parsed = urlparse(download_url)
                    file_name = os.path.basename(parsed.path).split('?')[0]
                
                file_type = determine_model_folder(
                    download_url,
                    file_name,
                    config.get('file_path', ''),
                    model_info.get('type', 'checkpoints')
                )
                
                downloads.append({
                    'file_url': download_url,
                    'file_name': file_name,
                    'file_type': file_type
                })
    
    # Fallback to model_configs.json format (simple url + filename)
    if not downloads:
        download_url = model_info.get('url') or model_info.get('download_url')
        if download_url:
            file_name = model_info.get('filename', '')
            if not file_name:
                parsed = urlparse(download_url)
                file_name = os.path.basename(parsed.path).split('?')[0]
            
            file_type = determine_model_folder(
                download_url,
                file_name,
                '',
                model_info.get('type', 'checkpoints')
            )
            
            downloads.append({
                'file_url': download_url,
                'file_name': file_name,
                'file_type': file_type
            })
    
    return downloads

def download_file(url: str, filepath: Path, headers: Optional[Dict[str, str]] = None, progress_callback=None) -> Tuple[bool, Optional[str]]:
    """
    Download a file from URL with progress reporting
    Returns: (success, error_message)
    """
    try:
        # Create directory if it doesn't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare headers
        request_headers = headers or {}
        
        # Add API keys if available for Hugging Face
        if 'huggingface.co' in url:
            hf_token = os.environ.get('HUGGING_FACE_API_KEY') or os.environ.get('HF_TOKEN')
            if hf_token:
                request_headers['Authorization'] = f"Bearer {hf_token}"
            
            # Add user agent to help with downloads
            request_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        # Add Civitai API key if needed
        if 'civitai.com' in url:
            civitai_key = os.environ.get('CIVITAI_API_KEY')
            if civitai_key:
                request_headers['Authorization'] = f"Bearer {civitai_key}"
        
        # Download with progress
        response = requests.get(url, headers=request_headers, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4):  # 32KB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        progress_callback(progress, downloaded, total_size, speed, eta)
        
        # Print completion
        size_mb = downloaded / (1024 * 1024)
        elapsed = time.time() - start_time
        speed_mb = size_mb / elapsed if elapsed > 0 else 0
        print(f"[OK] Downloaded {filepath.name} ({size_mb:.2f} MB in {elapsed:.1f}s @ {speed_mb:.2f} MB/s)", flush=True)
        
        return True, None
        
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.RequestException as e:
        return False, f"Download error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def verify_model_file(filepath: Path, expected_hash: Optional[str] = None) -> bool:
    """Verify downloaded model file with progress to avoid 'stuck on verify' UX for large files."""
    if not filepath.exists():
        return False
    
    if expected_hash:
        total_size = filepath.stat().st_size
        print(f"[VERIFY] Checking SHA256 hash for {filepath.name} ({total_size / (1024*1024):.2f} MB)...", flush=True)
        
        sha256_hash = hashlib.sha256()
        processed = 0
        last_report_pct = -1
        chunk_size = 32 * 1024 * 1024  # 32 MB chunks for better throughput
        start_time = time.time()
        
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    sha256_hash.update(chunk)
                    processed += len(chunk)
                    
                    if total_size > 0:
                        pct = int((processed / total_size) * 100)
                        # Report every 5% or on completion
                        if pct // 5 != last_report_pct // 5:
                            elapsed = time.time() - start_time
                            speed_mb_s = (processed / (1024*1024)) / elapsed if elapsed > 0 else 0.0
                            print(f"[VERIFY_PROGRESS] {pct}% ({processed/(1024*1024):.0f}/{total_size/(1024*1024):.0f} MB) @ {speed_mb_s:.2f} MB/s", flush=True)
                            last_report_pct = pct
        except Exception as e:
            print(f"[ERROR] Verification read error for {filepath.name}: {e}", flush=True)
            return False
        
        actual_hash = sha256_hash.hexdigest().upper()
        if actual_hash.upper() != expected_hash.upper():
            print(f"[ERROR] Hash mismatch! Expected: {expected_hash}, Got: {actual_hash}", flush=True)
            return False
        
        print(f"[OK] Hash verification passed for {filepath.name}", flush=True)
    
    return True

def get_dependencies(model_info: Dict[str, Any]) -> List[str]:
    """Extract dependencies from model config"""
    dependencies = []
    
    # Check for dependencies in model_info
    if 'dependencies' in model_info:
        deps = model_info['dependencies']
        if isinstance(deps, list):
            dependencies.extend([d for d in deps if d])
    
    # Check for dependencies in config
    if 'config' in model_info and 'dependencies' in model_info['config']:
        deps = model_info['config']['dependencies']
        if isinstance(deps, list):
            dependencies.extend([d for d in deps if d])
    
    return list(set(dependencies))  # Remove duplicates

def download_model(model_id: str, models_path: str, stable_diffusion_catalog: Dict[str, Any] = None, model_configs: Dict[str, Any] = None, downloaded_models: set = None) -> bool:
    """
    Download a single model (may have multiple files) and its dependencies
    Returns True if all files downloaded successfully
    """
    if downloaded_models is None:
        downloaded_models = set()
    
    # Skip if already downloaded in this session
    if model_id in downloaded_models:
        print(f"[SKIP] {model_id} already downloaded in this session", flush=True)
        return True
    
    print(f"\n[START] Downloading model: {model_id}", flush=True)
    
    # Try to find model in stable_diffusion.json first
    model_info = None
    if stable_diffusion_catalog and model_id in stable_diffusion_catalog:
        model_info = stable_diffusion_catalog[model_id]
    
    # Fallback to model_configs.json
    if not model_info and model_configs and model_id in model_configs:
        model_info = model_configs[model_id]
    
    if not model_info:
        print(f"[ERROR] Model {model_id} not found in catalog", flush=True)
        return False
    
    # Download dependencies first
    dependencies = get_dependencies(model_info)
    if dependencies:
        print(f"[INFO] {model_id} has {len(dependencies)} dependencies: {', '.join(dependencies)}", flush=True)
        for dep in dependencies:
            print(f"[DEPENDENCY] Downloading dependency: {dep}", flush=True)
            if not download_model(dep, models_path, stable_diffusion_catalog, model_configs, downloaded_models):
                print(f"[ERROR] Failed to download dependency {dep} for {model_id}", flush=True)
                return False
            print(f"[OK] Dependency {dep} downloaded successfully", flush=True)
    
    # Get all download URLs for this model
    downloads = get_download_urls_from_model(model_info, model_id)
    
    if not downloads:
        print(f"[ERROR] No download URLs found for {model_id}", flush=True)
        return False
    
    print(f"[INFO] Found {len(downloads)} file(s) to download for {model_id}", flush=True)
    
    # Download each file
    success_count = 0
    total_files = len(downloads)
    
    for idx, download_info in enumerate(downloads, 1):
        file_url = download_info['file_url']
        file_name = download_info['file_name']
        file_type = download_info['file_type']
        
        # Determine file path (normalize folder)
        file_type_norm = normalize_model_folder(file_type)
        filepath = Path(models_path) / file_type_norm / file_name
        alt_ckpt_path = Path(models_path) / 'ckpt' / file_name if file_type_norm == 'checkpoints' else None
        
        # Migrate legacy/alias locations to canonical folder if needed
        if file_type_norm == 'checkpoints' and alt_ckpt_path and alt_ckpt_path.exists() and not filepath.exists():
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                alt_ckpt_path.replace(filepath)
                print(f"[FIX] Moved legacy ckpt file to checkpoints: {file_name}", flush=True)
            except Exception as move_err:
                print(f"[WARN] Could not move legacy ckpt file: {move_err}", flush=True)
        
        print(f"[DOWNLOAD] [{idx}/{total_files}] {file_name} -> {file_type_norm}/", flush=True)
        print(f"[URL] {file_url}", flush=True)
        
        # Check if already exists
        if filepath.exists():
            print(f"[SKIP] File already exists: {filepath}", flush=True)
            success_count += 1
            continue
        
        # Get expected hash from config if available
        expected_hash = None
        if 'config' in model_info and 'files' in model_info['config']:
            for file_entry in model_info['config']['files']:
                if file_entry.get('path') == file_name:
                    expected_hash = file_entry.get('sha256sum') or file_entry.get('sha256')
                    break
        
        # Progress callback
        def progress_callback(progress, downloaded, total, speed, eta):
            size_mb = total / (1024 * 1024)
            downloaded_mb = downloaded / (1024 * 1024)
            speed_mb = speed / (1024 * 1024)
            
            eta_str = ""
            if eta > 0:
                if eta < 60:
                    eta_str = f"{eta:.0f}s"
                elif eta < 3600:
                    eta_str = f"{eta/60:.1f}m"
                else:
                    eta_str = f"{eta/3600:.1f}h"
            
            print(f"[PROGRESS] {progress:.1f}% ({downloaded_mb:.2f}/{size_mb:.2f} MB) @ {speed_mb:.2f} MB/s ETA: {eta_str}", flush=True)
        
        # Download the file
        success, error_msg = download_file(file_url, filepath, progress_callback=progress_callback)
        
        if not success:
            print(f"[ERROR] Failed to download {file_name}: {error_msg}", flush=True)
            if filepath.exists():
                filepath.unlink()  # Remove partial file
            continue
        
        # Verify the download
        if not verify_model_file(filepath, expected_hash):
            print(f"[ERROR] Verification failed for {file_name}", flush=True)
            filepath.unlink()  # Remove corrupted file
            continue
        
        success_count += 1
    
    # Mark model as downloaded
    if success_count == total_files:
        print(f"[OK] Successfully downloaded all {total_files} file(s) for {model_id}", flush=True)
        downloaded_models.add(model_id)
        return True
    else:
        print(f"[ERROR] Only downloaded {success_count}/{total_files} file(s) for {model_id}", flush=True)
        return False

def resolve_dependencies(model_id: str, catalog: Dict[str, Any], resolved: set = None) -> List[str]:
    """
    Recursively resolve model dependencies
    Returns list of model IDs to download (including dependencies)
    """
    if resolved is None:
        resolved = set()
    
    # Avoid circular dependencies
    if model_id in resolved:
        return []
    
    resolved.add(model_id)
    all_models = [model_id]
    
    # Get model info
    model_info = catalog.get(model_id)
    if not model_info:
        return [model_id]
    
    # Check for dependencies
    dependencies = model_info.get('dependencies', [])
    if dependencies and isinstance(dependencies, list):
        for dep_id in dependencies:
            if dep_id not in resolved:
                dep_models = resolve_dependencies(dep_id, catalog, resolved)
                # Add dependencies before the model that needs them
                all_models = dep_models + all_models
    
    return all_models

def download_models(model_ids: List[str], models_path: str, 
                   stable_diffusion_path: str = '/app/grid-image-model-reference/stable_diffusion.json',
                   config_path: str = '/app/comfy-bridge/model_configs.json',
                   resolve_deps: bool = True) -> bool:
    """Download multiple models with optional dependency resolution"""
    # Load catalogs
    stable_diffusion_catalog = None
    if os.path.exists(stable_diffusion_path):
        try:
            stable_diffusion_catalog = load_stable_diffusion_catalog(stable_diffusion_path)
            print(f"[INFO] Loaded {len(stable_diffusion_catalog)} models from stable_diffusion.json", flush=True)
        except Exception as e:
            print(f"[WARN] Could not load stable_diffusion.json: {e}", flush=True)
    
    model_configs = None
    if os.path.exists(config_path):
        try:
            model_configs = load_model_configs(config_path)
            print(f"[INFO] Loaded {len(model_configs)} models from model_configs.json", flush=True)
        except Exception as e:
            print(f"[WARN] Could not load model_configs.json: {e}", flush=True)
    
    if not stable_diffusion_catalog and not model_configs:
        print("[ERROR] No catalog files found", flush=True)
        return False
    
    # Check if models path exists
    models_path_obj = Path(models_path)
    if not models_path_obj.exists():
        print(f"[ERROR] Models path does not exist: {models_path}", flush=True)
        return False
    
    # Resolve dependencies if requested
    all_model_ids = []
    if resolve_deps:
        print(f"[INFO] Resolving dependencies for {len(model_ids)} model(s)...", flush=True)
        # Use stable_diffusion_catalog for dependency resolution as it has complete info
        catalog_for_deps = stable_diffusion_catalog or model_configs
        
        resolved_set = set()
        for model_id in model_ids:
            deps = resolve_dependencies(model_id, catalog_for_deps, resolved_set)
            for dep in deps:
                if dep not in all_model_ids:
                    all_model_ids.append(dep)
        
        if len(all_model_ids) > len(model_ids):
            added_deps = [m for m in all_model_ids if m not in model_ids]
            print(f"[INFO] Added {len(added_deps)} dependencies: {', '.join(added_deps)}", flush=True)
    else:
        all_model_ids = model_ids
    
    # Download each model (dependencies first, then requested models)
    success_count = 0
    total_count = len(all_model_ids)
    downloaded_models = set()  # Track downloaded models to avoid duplicates
    
    for model_id in all_model_ids:
        if download_model(model_id, models_path, stable_diffusion_catalog, model_configs, downloaded_models):
            success_count += 1
        else:
            print(f"[ERROR] Failed to download {model_id}", flush=True)
    
    print(f"\n[SUMMARY] Successfully downloaded: {success_count}/{total_count} models", flush=True)
    
    return success_count == total_count

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='Download models from catalog')
    parser.add_argument('--models', nargs='+', required=True, help='Model IDs to download')
    parser.add_argument('--models-path', default='/app/ComfyUI/models', help='Models directory path')
    parser.add_argument('--config', default='/app/comfy-bridge/model_configs.json', help='Model config file path')
    parser.add_argument('--stable-diffusion', default='/app/grid-image-model-reference/stable_diffusion.json', help='Stable diffusion catalog path')
    
    args = parser.parse_args()
    
    # Download models
    success = download_models(args.models, args.models_path, args.stable_diffusion, args.config)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()
