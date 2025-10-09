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
    """Load the model catalog from stable_diffusion.json"""
    repo_path = os.environ.get('GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH', '/app/grid-image-model-reference')
    catalog_path = os.path.join(repo_path, 'stable_diffusion.json')
    
    try:
        with open(catalog_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading catalog: {e}")
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
    """Download a file with retry logic"""
    if headers is None:
        headers = {}
    
    for attempt in range(max_retries):
        try:
            print(f"Downloading {os.path.basename(filepath)}... (attempt {attempt + 1})")
            
            response = requests.get(url, headers=headers, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgress: {percent:.1f}%", end='', flush=True)
            
            print(f"\n✅ Downloaded: {os.path.basename(filepath)}")
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
    print(f"\n🔄 Downloading model: {model_info['name']}")
    
    downloads = model_info['config'].get('download', [])
    if not downloads:
        print(f"❌ No download URLs found for {model_id}")
        return False
    
    success_count = 0
    total_files = len(downloads)
    
    for download in downloads:
        file_name = download['file_name']
        file_url = download['file_url']
        
        # Determine file type and directory
        file_type = 'checkpoint'  # Default
        for file_info in model_info['config'].get('files', []):
            if file_info.get('path') == file_name or file_info.get('file_name') == file_name:
                file_type = file_info.get('file_type', 'checkpoint')
                break
        
        target_dir = get_model_directory(file_type, models_path)
        file_path = os.path.join(target_dir, file_name)
        
        # Skip if file already exists
        if os.path.exists(file_path):
            print(f"⏭️  Skipping {file_name} (already exists)")
            success_count += 1
            continue
        
        # Get appropriate headers
        headers = get_api_headers(file_url, huggingface_key, civitai_key)
        
        # Download the file
        if download_file(file_url, file_path, headers):
            success_count += 1
        else:
            print(f"❌ Failed to download {file_name}")
    
    if success_count == total_files:
        print(f"✅ Successfully downloaded {model_info['name']}")
        return True
    else:
        print(f"⚠️  Downloaded {success_count}/{total_files} files for {model_info['name']}")
        return False

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
