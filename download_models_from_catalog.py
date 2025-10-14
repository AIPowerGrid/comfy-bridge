#!/usr/bin/env python3
"""
Download models from the AI Power Grid model catalog using HuggingFace and Civitai APIs.
"""

import os
import sys
import json
import requests
import argparse
from pathlib import Path
from urllib.parse import urlparse
import time

def load_catalog():
    """Load the model catalog from model_configs.json"""
    catalog_path = '/app/comfy-bridge/model_configs.json'
    
    try:
        with open(catalog_path, 'r') as f:
            catalog = json.load(f)
            print(f"✅ Loaded catalog from: {catalog_path}")
            return catalog
    except Exception as e:
        print(f"❌ Error loading catalog from {catalog_path}: {e}")
        return {}

def get_api_headers(url, huggingface_key=None, civitai_key=None):
    """Get appropriate headers for API requests"""
    headers = {
        'User-Agent': 'AI-Power-Grid-Worker/1.0'
    }
    
    if 'huggingface.co' in url and huggingface_key:
        headers['Authorization'] = f'Bearer {huggingface_key}'
    elif 'civitai.com' in url and civitai_key:
        headers['Authorization'] = f'Bearer {civitai_key}'
    
    return headers

def download_file(url, filepath, headers=None, max_retries=3):
    """Download a file with retry logic and detailed progress"""
    if headers is None:
        headers = {}
    
    def format_bytes(bytes_val):
        """Format bytes to human readable format"""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"
    
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(filepath)
            print(f"Downloading {filename}... (attempt {attempt + 1})")
            
            response = requests.get(url, headers=headers, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            last_update = start_time
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        current_time = time.time()
                        
                        # Update progress every 0.5 seconds to avoid spam
                        if current_time - last_update >= 0.5 or downloaded == total_size:
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                elapsed = current_time - start_time
                                speed = downloaded / elapsed if elapsed > 0 else 0
                                
                                # Calculate ETA
                                if speed > 0 and downloaded < total_size:
                                    remaining = total_size - downloaded
                                    eta_seconds = remaining / speed
                                    eta_str = f"ETA: {int(eta_seconds//60)}m{int(eta_seconds%60)}s"
                                else:
                                    eta_str = "ETA: --"
                                
                                progress_str = (
                                    f"\r[{percent:5.1f}%] {format_bytes(downloaded)}/{format_bytes(total_size)} "
                                    f"({format_bytes(speed)}/s) {eta_str}"
                                )
                                print(progress_str, end='', flush=True)
                            last_update = current_time
            
            print(f"\n✅ Downloaded: {filename}")
            return True
            
        except Exception as e:
            print(f"\n❌ Download failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return False
    
    return False

def get_model_directory(file_type, models_path):
    """Get the appropriate directory for a model file type"""
    type_mapping = {
        'checkpoint': 'checkpoints',
        'vae': 'vae',
        'clip': 'clip',
        'lora': 'loras',
        'unet': 'unet',
        'diffusion': 'diffusion_models',
        'text_encoder': 'text_encoders',
        'stable_cascade_stage_b': 'checkpoints',
        'stable_cascade_stage_c': 'checkpoints',
    }
    
    directory = type_mapping.get(file_type, 'checkpoints')
    full_path = os.path.join(models_path, directory)
    os.makedirs(full_path, exist_ok=True)
    return full_path

def download_model(model_id, catalog, models_path, huggingface_key=None, civitai_key=None):
    """Download a specific model from the catalog"""
    if model_id not in catalog:
        print(f"❌ Model '{model_id}' not found in catalog")
        return False
    
    model_info = catalog[model_id]
    print(f"\n🔄 Downloading model: {model_id}")
    
    # Get main model file info
    filename = model_info.get('filename', f"{model_id}.safetensors")
    url = model_info.get('url')
    file_type = model_info.get('type', 'checkpoints')
    
    if not url:
        print(f"❌ No download URL found for {model_id}")
        return False
    
    success_count = 0
    total_files = 1 + len(model_info.get('dependencies', []))
    
    # Download main model file
    target_dir = get_model_directory(file_type, models_path)
    file_path = os.path.join(target_dir, filename)
    
    if os.path.exists(file_path):
        print(f"⏭️  Skipping {filename} (already exists)")
        success_count += 1
    else:
        print(f"Downloading {filename}... (attempt 1)")
        headers = get_api_headers(url, huggingface_key, civitai_key)
        if download_file(url, file_path, headers):
            success_count += 1
        else:
            print(f"❌ Failed to download {filename}")
    
    # Download dependencies
    for dep in model_info.get('dependencies', []):
        dep_filename = dep.get('filename', '')
        dep_url = dep.get('url', '')
        dep_type = dep.get('type', 'checkpoints')
        
        if not dep_filename or not dep_url:
            continue
        
        dep_target_dir = get_model_directory(dep_type, models_path)
        dep_file_path = os.path.join(dep_target_dir, dep_filename)
        
        # Skip if file already exists
        if os.path.exists(dep_file_path):
            print(f"⏭️  Skipping {dep_filename} (already exists)")
            success_count += 1
            continue
        
        # Get appropriate headers
        headers = get_api_headers(dep_url, huggingface_key, civitai_key)
        
        # Download the dependency
        print(f"Downloading {dep_filename}... (attempt 1)")
        if download_file(dep_url, dep_file_path, headers):
            success_count += 1
        else:
            print(f"❌ Failed to download {dep_filename}")
    
    if success_count == total_files:
        print(f"✅ Successfully downloaded {model_id}")
        return True
    else:
        print(f"⚠️  Downloaded {success_count}/{total_files} files for {model_id}")
        return success_count > 0

def main():
    parser = argparse.ArgumentParser(description='Download models from AI Power Grid catalog')
    parser.add_argument('--models', required=True, help='Comma-separated list of model IDs to download')
    parser.add_argument('--models-path', default='/app/ComfyUI/models', help='Path to models directory')
    
    args = parser.parse_args()
    
    # Get API keys from environment
    huggingface_key = os.environ.get('HUGGING_FACE_API_KEY')
    civitai_key = os.environ.get('CIVITAI_API_KEY')
    
    if not huggingface_key and not civitai_key:
        print("❌ No API keys found. Please set HUGGING_FACE_API_KEY and/or CIVITAI_API_KEY")
        return 1
    
    # Load catalog
    catalog = load_catalog()
    if not catalog:
        print("❌ Failed to load model catalog")
        return 1
    
    # Parse model list
    model_ids = [m.strip() for m in args.models.split(',') if m.strip()]
    
    if not model_ids:
        print("❌ No models specified")
        return 1
    
    print(f"🎯 Downloading {len(model_ids)} models...")
    print(f"📁 Models directory: {args.models_path}")
    
    success_count = 0
    for model_id in model_ids:
        if download_model(model_id, catalog, args.models_path, huggingface_key, civitai_key):
            success_count += 1
    
    print(f"\n🎉 Downloaded {success_count}/{len(model_ids)} models successfully")
    
    if success_count == len(model_ids):
        return 0
    else:
        return 1

if __name__ == '__main__':
    sys.exit(main())
