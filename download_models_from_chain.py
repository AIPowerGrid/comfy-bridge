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

# Throttle progress messages to reduce log spam
_last_progress_time = {}
_progress_throttle_interval = 2.0  # Only emit progress every 2 seconds

def emit_progress(progress: float, speed: str = "", eta: str = "", message: str = "", msg_type: str = "info"):
    """Emit a JSON progress message for the management UI.
    
    Throttles progress updates to reduce log spam - only emits every 2 seconds
    unless it's an error, warning, or completion message.
    """
    global _last_progress_time
    
    # Always emit errors, warnings, and important messages
    is_important = msg_type in ("error", "warning") or "ERROR" in message.upper() or "WARN" in message.upper()
    is_completion = progress >= 100 or "SUCCESS" in message.upper() or "COMPLETE" in message.upper()
    
    # Throttle regular progress updates
    if not is_important and not is_completion:
        now = time.time()
        last_time = _last_progress_time.get(_current_model, 0)
        if now - last_time < _progress_throttle_interval:
            return  # Skip this update
        _last_progress_time[_current_model] = now
    
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
    from model_catalog import get_catalog_model, CatalogModel, MODEL_CATALOG
    CATALOG_AVAILABLE = True
    # Debug: Verify catalog is loaded
    catalog_size = len(MODEL_CATALOG) if MODEL_CATALOG else 0
    if catalog_size == 0:
        print(f"[WARN] MODEL_CATALOG is empty! This indicates an import or initialization issue.")
        # Try importing the sub-dictionaries to see if they exist
        try:
            from model_catalog import WAN_MODELS, FLUX_MODELS
            wan_size = len(WAN_MODELS) if WAN_MODELS else 0
            flux_size = len(FLUX_MODELS) if FLUX_MODELS else 0
            print(f"[DEBUG] WAN_MODELS size: {wan_size}, FLUX_MODELS size: {flux_size}")
        except ImportError as e:
            print(f"[DEBUG] Could not import WAN_MODELS/FLUX_MODELS: {e}")
    elif "wan2.2_ti2v_5B" not in MODEL_CATALOG:
        # Log available keys for debugging
        wan_keys = [k for k in MODEL_CATALOG.keys() if 'wan2' in k.lower() or 'wan' in k.lower()]
        all_keys = list(MODEL_CATALOG.keys())[:10]  # First 10 keys
        print(f"[DEBUG] wan2.2_ti2v_5B not in catalog. Catalog size: {catalog_size}")
        print(f"[DEBUG] Available WAN keys: {wan_keys}")
        print(f"[DEBUG] Sample catalog keys: {all_keys}")
except ImportError as e:
    CATALOG_AVAILABLE = False
    print(f"[INFO] Fallback model catalog not available: {e}")
except Exception as e:
    CATALOG_AVAILABLE = False
    print(f"[ERROR] Error loading catalog: {e}")
    import traceback
    traceback.print_exc()


def get_model_dependencies(model_name: str, models_path: str) -> List[Dict[str, str]]:
    """
    Detect dependencies required by a model's workflow file.
    Returns list of dependency info dicts: [{"name": "...", "type": "...", "file": "..."}, ...]
    """
    dependencies = []
    
    try:
        from comfy_bridge.model_mapper import get_workflow_file
        from comfy_bridge.workflow import detect_workflow_model_type
        from comfy_bridge.config import Settings
        import json
        
        # Get workflow file
        workflow_filename = get_workflow_file(model_name)
        workflow_path = Path(Settings.WORKFLOW_DIR) / workflow_filename
        
        if not workflow_path.exists():
            return dependencies
        
        # Load workflow
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)
        
        model_type = detect_workflow_model_type(workflow)
        
        # Flux models need T5XXL, clip_l, and ae.safetensors
        if model_type == "flux":
            # Check for DualCLIPLoader to find required text encoders
            nodes = workflow.get("nodes", []) if isinstance(workflow, dict) and "nodes" in workflow else list(workflow.values())
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                class_type = node.get("class_type") or node.get("type", "")
                
                if class_type == "DualCLIPLoader":
                    inputs = node.get("inputs", {})
                    # Check clip_name2 (T5XXL)
                    clip2 = inputs.get("clip_name2", "")
                    if clip2 and ("t5xxl" in clip2.lower() or "xxl" in clip2.lower()):
                        text_encoder_path = Path(models_path) / "text_encoders" / clip2
                        if not text_encoder_path.exists():
                            dependencies.append({
                                "name": "T5XXL Text Encoder",
                                "type": "text_encoder",
                                "file": clip2,
                                "required_for": model_name
                            })
                    
                    # Check clip_name1 (CLIP-L)
                    clip1 = inputs.get("clip_name1", "")
                    if clip1 and "clip_l" in clip1.lower():
                        clip_path = Path(models_path) / "text_encoders" / clip1
                        if not clip_path.exists():
                            dependencies.append({
                                "name": "CLIP-L Text Encoder",
                                "type": "text_encoder",
                                "file": clip1,
                                "required_for": model_name
                            })
                
                elif class_type == "VAELoader":
                    inputs = node.get("inputs", {})
                    vae_name = inputs.get("vae_name", "")
                    if vae_name == "ae.safetensors":
                        vae_path = Path(models_path) / "vae" / vae_name
                        if not vae_path.exists():
                            dependencies.append({
                                "name": "Flux VAE",
                                "type": "vae",
                                "file": vae_name,
                                "required_for": model_name
                            })
        
    except Exception as e:
        # Don't fail if dependency detection fails
        print(f"[DEBUG] Could not detect dependencies for {model_name}: {e}")
    
    return dependencies


def download_dependency(dep_info: Dict[str, str], models_path: str) -> bool:
    """
    Download a single dependency file.
    Returns True if successful.
    """
    dep_name = dep_info["name"]
    dep_file = dep_info["file"]
    dep_type = dep_info["type"]
    
    # Map dependency types to download URLs
    # These are common shared dependencies
    dependency_urls = {
        "t5xxl_fp16.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
        "t5xxl_fp8_e4m3fn.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        "clip_l.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "ae.safetensors": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
    }
    
    # Check if we have a URL for this dependency
    download_url = dependency_urls.get(dep_file)
    if not download_url:
        emit_progress(0, message=f"[SKIP] No download URL for dependency: {dep_file}", msg_type="warning")
        return False
    
    # Determine target directory
    if dep_type == "text_encoder":
        target_dir = Path(models_path) / "text_encoders"
    elif dep_type == "vae":
        target_dir = Path(models_path) / "vae"
    else:
        target_dir = Path(models_path) / dep_type
    
    target_path = target_dir / dep_file
    
    # Check if already exists (don't log - already checked before calling)
    if target_path.exists() and _is_file_complete(target_path):
        return True
    
    # Download the dependency
    emit_progress(0, message=f"  → Downloading {dep_name}...")
    
    success, error = download_file(download_url, target_path, expected_hash=None, progress_callback=None)
    
    if not success:
        emit_progress(0, message=f"  ✗ Failed to download {dep_name}: {error}", msg_type="error")
    
    return success


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
        
        # For HuggingFace, try using 'raw' endpoint if 'resolve' fails or gives wrong size
        # Some HuggingFace repos serve incomplete files via 'resolve' for large files
        original_url = url
        if 'huggingface.co' in url and '/resolve/' in url:
            # Try alternative: replace 'resolve' with 'raw' for more reliable downloads
            # But keep resolve as primary since it's more common
            pass
        
        response = requests.get(url, headers=request_headers, stream=True, timeout=300, allow_redirects=True)
        response.raise_for_status()
        
        # Check content type - if HTML, it's likely an error page
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type:
            return False, "Received HTML instead of file - check if API key is required (set CIVITAI_API_KEY for CivitAI)"
        
        total_size = int(response.headers.get('content-length', 0))
        
        # Only log warnings for suspicious sizes (reduce spam)
        if total_size > 0:
            # Warn if server reports a suspiciously small size for a large model file
            if total_size < 5_000_000_000 and 'wan2' in filepath.name.lower() and 'ti2v' in filepath.name.lower():
                print(f"[WARN] Server reports file size of only {total_size / 1e9:.2f}GB - this may be incomplete!", flush=True)
        elif total_size == 0:
            # Only warn if it's a large file that should have content-length
            pass  # Don't spam logs for missing content-length
        
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
            print(f"[ERROR] Download incomplete: expected {total_size / 1e9:.2f}GB, got {downloaded / 1e9:.2f}GB", flush=True)
            filepath.unlink(missing_ok=True)
            return False, f"Incomplete download: expected {total_size / 1e9:.2f}GB, got {downloaded / 1e9:.2f}GB"
        
        # Additional verification: if content-length was 0 or missing, verify file size is reasonable
        # Large model files should be at least 100MB
        if total_size == 0 and downloaded < 100_000_000:
            print(f"[ERROR] Downloaded file too small: {downloaded / 1e6:.2f}MB", flush=True)
            filepath.unlink(missing_ok=True)
            return False, f"Downloaded file too small: {downloaded / 1e6:.2f}MB (expected large model file)"
        
        # Verify hash if provided (silently, only log on failure)
        if expected_hash and len(expected_hash) == 64:
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(32 * 1024 * 1024), b''):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().upper()
            if actual_hash != expected_hash.upper():
                print(f"[ERROR] Hash mismatch! Expected: {expected_hash}, Got: {actual_hash}", flush=True)
                filepath.unlink(missing_ok=True)
                return False, "Hash verification failed"
        
        # Only log completion for large files or if verbose mode
        size_mb = downloaded / (1024 * 1024)
        if size_mb > 100:  # Only log files > 100MB
            elapsed = time.time() - start_time
            speed_mb = size_mb / elapsed if elapsed > 0 else 0
            print(f"[OK] {filepath.name} ({size_mb:.1f}MB @ {speed_mb:.1f}MB/s)", flush=True)
        
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
    
    # Check for dependencies (e.g., T5XXL for Flux models)
    dependencies = get_model_dependencies(model_info.display_name, models_path)
    missing_deps = []
    if dependencies:
        for dep in dependencies:
            dep_path = Path(models_path) / ("text_encoders" if dep["type"] == "text_encoder" else dep["type"]) / dep["file"]
            if not dep_path.exists():
                missing_deps.append(dep)
    
    # Check if model files exist
    all_model_files_exist = True
    if model_info.files:
        for file_info in model_info.files:
            folder = normalize_model_folder(file_info.file_type)
            filepath = Path(models_path) / folder / file_info.file_name
            if not (filepath.exists() and _is_file_complete(filepath)):
                all_model_files_exist = False
                break
    
    # If everything exists, just log success and return
    if not missing_deps and all_model_files_exist and model_info.files:
        total_files = len(model_info.files)
        emit_progress(100, message=f"✓ {model_info.display_name} - All files found ({total_files} files)")
        downloaded.add(model_info.display_name)
        return True
    
    # Need to download something - log model name
    if missing_deps or not all_model_files_exist:
        emit_progress(0, message=f"[MODEL] {model_info.display_name}")
        
        # Download missing dependencies
        if missing_deps:
            emit_progress(0, message=f"  Dependencies: {len(missing_deps)} missing, downloading...")
            for dep in missing_deps:
                download_dependency(dep, models_path)
    
    # Check if model has download files
    if not model_info.files:
        emit_progress(0, message=f"[WARN] No download files registered for {model_info.display_name}", msg_type="warning")
        emit_progress(0, message=f"  This model needs to be registered with download URLs (V2 contract)", msg_type="warning")
        return False
    
    success_count = 0
    total_files = len(model_info.files)
    
    # First pass: check if all files already exist
    all_exist = True
    for file_info in model_info.files:
        folder = normalize_model_folder(file_info.file_type)
        filepath = Path(models_path) / folder / file_info.file_name
        if not (filepath.exists() and _is_file_complete(filepath)):
            all_exist = False
            break
    
    # If all files exist, just log success and return
    if all_exist:
        emit_progress(100, message=f"✓ All files found ({total_files} files)")
        downloaded.add(model_info.display_name)
        return True
    
    # Some files need downloading - proceed with download
    files_downloaded = False
    for idx, file_info in enumerate(model_info.files, 1):
        folder = normalize_model_folder(file_info.file_type)
        filepath = Path(models_path) / folder / file_info.file_name
        
        # Calculate base progress for this file
        file_base_progress = ((idx - 1) / total_files) * 100
        file_progress_range = 100 / total_files
        
        # Check if already exists (silently skip)
        if filepath.exists() and _is_file_complete(filepath):
            success_count += 1
            continue
        
        files_downloaded = True  # Mark that we're downloading something
        
        # Remove incomplete file
        if filepath.exists():
            filepath.unlink()
        
        # Download with progress output
        last_emit_time = [0]  # Use list to allow modification in nested function
        
        def progress_cb(pct, dl, total, speed, eta):
            # Throttle progress updates to every 2 seconds (reduced spam)
            now = time.time()
            if now - last_emit_time[0] < 2.0 and pct < 99:
                return
            last_emit_time[0] = now
            
            speed_mb = speed / (1024 * 1024)
            speed_str = f"{speed_mb:.1f} MB/s"
            eta_str = f"{eta:.0f}s" if eta < 60 else f"{eta/60:.1f}m"
            
            # Calculate overall progress including file position
            overall_pct = file_base_progress + (pct / 100) * file_progress_range
            
            # More concise message
            message = f"  [{pct:.0f}%] {file_info.file_name}"
            emit_progress(overall_pct, speed=speed_str, eta=eta_str, message=message)
        
        # Try primary URL (don't log URL to reduce spam)
        emit_progress(file_base_progress, message=f"  Downloading {file_info.file_name}...")
        success, error = download_file(
            file_info.download_url,
            filepath,
            file_info.sha256_hash,
            progress_cb
        )
        
        # Try mirror if primary fails
        if not success and file_info.mirror_url:
            emit_progress(file_base_progress, message=f"  Trying mirror URL...")
            success, error = download_file(
                file_info.mirror_url,
                filepath,
                file_info.sha256_hash,
                progress_cb
            )
        
        if success:
            success_count += 1
            emit_progress(file_base_progress + file_progress_range, message=f"  ✓ {file_info.file_name}")
        else:
            emit_progress(file_base_progress, message=f"  ✗ {file_info.file_name}: {error}", msg_type="error")
    
    downloaded.add(model_info.display_name)
    final_success = success_count == total_files
    
    # Only log if we actually downloaded files (all-exists case already logged above)
    if files_downloaded:
        if final_success:
            emit_progress(100, message=f"✓ {model_info.display_name} - {success_count}/{total_files} files")
        else:
            emit_progress(100, message=f"⚠ {model_info.display_name} - {success_count}/{total_files} files", msg_type="warning")
    
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
        
        # For HuggingFace URLs, prepare alternative URLs in case primary fails or gives wrong size
        alternative_urls = []
        if 'huggingface.co' in download_url:
            # Extract repo and file path
            if '/resolve/' in download_url:
                parts = download_url.split('/resolve/')
                if len(parts) == 2:
                    repo_part = parts[0]
                    file_part = parts[1]
                    # Try without 'split_files' path if present
                    if 'split_files' in file_part:
                        alt_file_part = file_part.replace('/split_files', '')
                        alternative_urls.append(f"{repo_part}/resolve/{alt_file_part}")
                    # Try with 'raw' instead of 'resolve' (sometimes more reliable for large files)
                    alternative_urls.append(f"{repo_part}/raw/{file_part}")
        
        success, error = download_file(download_url, target_path, progress_callback=emit_progress)
        
        # If download succeeded but file size is wrong, try alternatives
        if success and file_info.size_bytes > 0:
            actual_size = target_path.stat().st_size
            expected_size = file_info.size_bytes
            size_diff_pct = abs(actual_size - expected_size) / expected_size * 100
            
            # If size mismatch is significant (>10%), try alternative URLs
            if size_diff_pct > 10 and alternative_urls:
                emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - Size mismatch detected ({actual_size / 1e9:.2f}GB vs expected {expected_size / 1e9:.2f}GB), trying alternative URL...")
                target_path.unlink(missing_ok=True)
                success = False
                
                for alt_url in alternative_urls:
                    emit_progress(0, message=f"  [{idx}/{total_files}] Trying alternative URL: {alt_url[:80]}...")
                    success, error = download_file(alt_url, target_path, progress_callback=emit_progress)
                    if success:
                        # Verify size again
                        actual_size = target_path.stat().st_size
                        size_diff_pct = abs(actual_size - expected_size) / expected_size * 100
                        if size_diff_pct <= 10:
                            emit_progress(0, message=f"  [{idx}/{total_files}] Alternative URL worked! File size: {actual_size / 1e9:.2f}GB")
                            break
                        else:
                            emit_progress(0, message=f"  [{idx}/{total_files}] Alternative URL also has size mismatch, trying next...")
                            target_path.unlink(missing_ok=True)
                            success = False
                    if success:
                        break
        
        if success:
            # Verify file size matches expected size
            if file_info.size_bytes > 0:
                actual_size = target_path.stat().st_size
                expected_size = file_info.size_bytes
                size_diff_pct = abs(actual_size - expected_size) / expected_size * 100
                
                # For large files (>1GB), allow 5% tolerance; for smaller files, allow 10%
                tolerance = 5 if expected_size > 1_000_000_000 else 10
                
                if size_diff_pct > tolerance:
                    emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - SIZE MISMATCH! Expected {expected_size / 1e9:.2f}GB, got {actual_size / 1e9:.2f}GB ({size_diff_pct:.1f}% difference)", msg_type="error")
                    emit_progress(0, message=f"  [{idx}/{total_files}] File appears incomplete or corrupted. Removing and will retry on next run.", msg_type="error")
                    target_path.unlink(missing_ok=True)
                    success = False
                    error = f"File size mismatch: expected {expected_size / 1e9:.2f}GB, got {actual_size / 1e9:.2f}GB"
                else:
                    emit_progress(100, message=f"  [{idx}/{total_files}] {file_name} - downloaded successfully ({actual_size / 1e9:.2f}GB)")
            else:
                # If no expected size, at least verify it's not suspiciously small
                actual_size = target_path.stat().st_size
                if actual_size < 100_000_000:  # Less than 100MB is suspicious for a model file
                    emit_progress(0, message=f"  [{idx}/{total_files}] {file_name} - WARNING: File is very small ({actual_size / 1e6:.2f}MB), may be incomplete", msg_type="warning")
                emit_progress(100, message=f"  [{idx}/{total_files}] {file_name} - downloaded successfully ({actual_size / 1e9:.2f}GB)")
            
            if success:
                downloaded.add(file_name)
                success_count += 1
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
                emit_progress(0, message=f"[CATALOG] Checking fallback catalog for '{model.display_name}' (no blockchain files)...")
                catalog_model = get_catalog_model(model.display_name)
                found_in_catalog = False
                
                if catalog_model:
                    emit_progress(0, message=f"  ✓ Found '{model.display_name}' in catalog, using catalog download URLs")
                    models_to_download.remove(model)
                    catalog_downloads.append((model.display_name, catalog_model))
                    found_in_catalog = True
                else:
                    # Try alternative name variations (common patterns for WAN models)
                    # IMPORTANT: Try the exact catalog key FIRST for best performance
                    name_variations = [
                        "wan2.2_ti2v_5B",  # Direct catalog key - try FIRST
                        model.display_name.replace('_', '.'),  # wan2_2_ti2v_5B -> wan2.2.ti2v.5B
                        model.display_name.replace('_', '-'),  # wan2_2_ti2v_5B -> wan2-2-ti2v-5B
                        model.display_name.replace('.', '_'),  # wan2.2_ti2v_5B -> wan2_2_ti2v_5B
                        model.display_name.replace('.', '-'),  # wan2.2_ti2v_5B -> wan2-2-ti2v-5B
                        model.display_name.lower(),           # wan2_2_ti2v_5B -> wan2_2_ti2v_5b
                        # Try with dots instead of underscores for numbers
                        model.display_name.replace('_2_', '.2.').replace('_', '.'),  # wan2_2_ti2v_5B -> wan2.2.ti2v.5B
                        model.display_name.replace('_2_', '-2-').replace('_', '-'),  # wan2_2_ti2v_5B -> wan2-2-ti2v-5B
                        # Try normalized versions
                        model.display_name.replace('_', '.').replace('-', '.').lower(),  # wan2_2_ti2v_5B -> wan2.2.ti2v.5b
                        "wan2.2-ti2v-5B",  # Hyphen variant
                    ]
                    # Remove duplicates and the original
                    name_variations = list(dict.fromkeys([v for v in name_variations if v != model.display_name]))
                    
                    for variant in name_variations:
                        catalog_model = get_catalog_model(variant)
                        if catalog_model:
                            emit_progress(0, message=f"  ✓ Found '{model.display_name}' in catalog as '{variant}'")
                            models_to_download.remove(model)
                            catalog_downloads.append((model.display_name, catalog_model))
                            found_in_catalog = True
                            break
                        # Debug: Check if exact key exists
                        if variant == "wan2.2_ti2v_5B":
                            try:
                                from model_catalog import MODEL_CATALOG
                                if variant in MODEL_CATALOG:
                                    emit_progress(0, message=f"  [DEBUG] Key '{variant}' exists in MODEL_CATALOG")
                                else:
                                    available_keys = [k for k in MODEL_CATALOG.keys() if 'wan2' in k.lower()]
                                    emit_progress(0, message=f"  [DEBUG] Key '{variant}' NOT in MODEL_CATALOG. Available WAN keys: {available_keys}")
                            except Exception as e:
                                emit_progress(0, message=f"  [DEBUG] Error checking catalog: {e}")
                
                if not found_in_catalog:
                    # Show which variations were tried (if we have them)
                    tried_variations = name_variations if 'name_variations' in locals() else []
                    emit_progress(0, message=f"  ✗ '{model.display_name}' not found in catalog", msg_type="warning")
                    if tried_variations:
                        emit_progress(0, message=f"    Tried variations: {', '.join(tried_variations[:5])}...", msg_type="warning")
    
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
