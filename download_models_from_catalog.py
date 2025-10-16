#!/usr/bin/env python3
"""
Model Download Script for ComfyUI Bridge
Downloads models from various sources based on catalog configuration
"""

import json
import os
import sys
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import hashlib
import time

def load_model_configs(config_path: str = 'model_configs.json') -> Dict[str, Any]:
    """Load model configurations from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {config_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing {config_path}: {e}")
        sys.exit(1)

def get_download_url(model_config: Dict[str, Any]) -> Optional[str]:
    """Get download URL for a model"""
    # Try different URL fields
    url_fields = ['download_url', 'url', 'huggingface_url', 'civitai_url']
    
    for field in url_fields:
        if field in model_config and model_config[field]:
            return model_config[field]
    
    return None

def get_model_filename(model_config: Dict[str, Any], model_id: str) -> str:
    """Get filename for downloaded model"""
    if 'filename' in model_config:
        return model_config['filename']
    
    # Extract filename from URL
    url = get_download_url(model_config)
    if url:
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        if filename and '.' in filename:
            return filename
    
    # Default filename
    return f"{model_id}.safetensors"

def get_model_path(model_config: Dict[str, Any], models_path: str) -> Path:
    """Get full path for model file"""
    model_type = model_config.get('type', 'checkpoints')
    filename = get_model_filename(model_config, model_config.get('id', 'unknown'))
    
    return Path(models_path) / model_type / filename

def download_file(url: str, filepath: Path, headers: Optional[Dict[str, str]] = None) -> bool:
    """Download a file from URL"""
    try:
        print(f"Downloading {url} to {filepath}")
        
        # Create directory if it doesn't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare headers
        request_headers = headers or {}
        
        # Add API keys if available
        if 'huggingface.co' in url and os.environ.get('HUGGING_FACE_API_KEY'):
            request_headers['Authorization'] = f"Bearer {os.environ['HUGGING_FACE_API_KEY']}"
        elif 'civitai.com' in url and os.environ.get('CIVITAI_API_KEY'):
            request_headers['Authorization'] = f"Bearer {os.environ['CIVITAI_API_KEY']}"
        
        # Download with progress
        response = requests.get(url, headers=request_headers, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}% ({downloaded}/{total_size} bytes)", end='', flush=True)
        
        print()  # New line after progress
        print(f"Downloaded: {filepath}")
        return True
        
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def verify_model(model_config: Dict[str, Any], filepath: Path) -> bool:
    """Verify downloaded model"""
    if 'sha256' in model_config:
        expected_hash = model_config['sha256']
        print(f"Verifying SHA256 hash...")
        
        sha256_hash = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        actual_hash = sha256_hash.hexdigest()
        if actual_hash.lower() != expected_hash.lower():
            print(f"Hash mismatch! Expected: {expected_hash}, Got: {actual_hash}")
            return False
        
        print("Hash verification passed")
    
    return True

def download_model(model_id: str, model_config: Dict[str, Any], models_path: str) -> bool:
    """Download a single model"""
    print(f"\n=== Downloading {model_id} ===")
    
    # Get download URL
    url = get_download_url(model_config)
    if not url:
        print(f"No download URL found for {model_id}")
        return False
    
    # Get file path
    filepath = get_model_path(model_config, models_path)
    
    # Check if already exists
    if filepath.exists():
        print(f"Model already exists: {filepath}")
        if verify_model(model_config, filepath):
            return True
        else:
            print("Existing file failed verification, re-downloading...")
            filepath.unlink()
    
    # Download the file
    if not download_file(url, filepath):
        return False
    
    # Verify the download
    if not verify_model(model_config, filepath):
        filepath.unlink()  # Remove corrupted file
        return False
    
    print(f"Successfully downloaded {model_id}")
    return True

def download_models(model_ids: List[str], models_path: str, config_path: str = 'model_configs.json') -> bool:
    """Download multiple models"""
    configs = load_model_configs(config_path)
    
    success_count = 0
    total_count = len(model_ids)
    
    for model_id in model_ids:
        if model_id not in configs:
            print(f"Model {model_id} not found in catalog")
            continue
        
        if download_model(model_id, configs[model_id], models_path):
            success_count += 1
        else:
            print(f"Failed to download {model_id}")
    
    print(f"\n=== Download Summary ===")
    print(f"Successfully downloaded: {success_count}/{total_count} models")
    
    return success_count == total_count

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='Download models from catalog')
    parser.add_argument('--models', nargs='+', required=True, help='Model IDs to download')
    parser.add_argument('--models-path', default='/app/ComfyUI/models', help='Models directory path')
    parser.add_argument('--config', default='model_configs.json', help='Model config file path')
    
    args = parser.parse_args()
    
    # Check if models path exists
    models_path = Path(args.models_path)
    if not models_path.exists():
        print(f"Models path does not exist: {models_path}")
        sys.exit(1)
    
    # Download models
    success = download_models(args.models, str(models_path), args.config)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()
