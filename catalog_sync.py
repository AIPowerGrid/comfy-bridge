#!/usr/bin/env python3
"""
Catalog Sync Script for ComfyUI Bridge
Syncs model catalog from remote repository
"""

import json
import os
import sys
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import time

def load_catalog_config() -> Dict[str, Any]:
    """Load catalog configuration from environment"""
    return {
        'repository_path': os.environ.get('GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH', '/app/grid-image-model-reference'),
        'catalog_file': 'model_configs.json',
        'sync_interval': int(os.environ.get('CATALOG_SYNC_INTERVAL', '3600')),  # 1 hour default
        'auto_sync': os.environ.get('CATALOG_AUTO_SYNC', 'true').lower() == 'true'
    }

def sync_catalog_from_git(repo_path: str) -> bool:
    """Sync catalog from git repository"""
    try:
        repo_dir = Path(repo_path)
        
        if not repo_dir.exists():
            print(f"Repository path does not exist: {repo_path}")
            return False
        
        # Change to repository directory
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            # Try to pull latest changes, but don't fail if it's read-only
            try:
                result = subprocess.run(['git', 'pull'], capture_output=True, text=True, check=True)
                print("Catalog synced from git repository")
            except subprocess.CalledProcessError as e:
                print(f"Git pull failed (likely read-only mount): {e.stderr}")
                print("Continuing with existing catalog files...")
            
            # Convert the comprehensive catalog to our simple format
            return convert_comprehensive_catalog(repo_path)
            
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        print(f"Error syncing catalog: {e}")
        return False

def convert_comprehensive_catalog(repo_path: str) -> bool:
    """Convert comprehensive catalog to simple format"""
    try:
        import json
        
        # Load comprehensive catalogs
        catalog_files = [
            'stable_diffusion.json',
            'stable_diffusion_old.json',
            'lora.json',
            'controlnet.json',
            'miscellaneous.json'
        ]
        
        simple_catalog = {}
        
        for catalog_file in catalog_files:
            catalog_path = Path(repo_path) / catalog_file
            if catalog_path.exists():
                print(f"Processing {catalog_file}...")
                
                with open(catalog_path, 'r') as f:
                    comprehensive_data = json.load(f)
                
                # Handle different data formats
                if isinstance(comprehensive_data, dict):
                    # Dictionary format - each key is a model ID
                    models_data = comprehensive_data.items()
                elif isinstance(comprehensive_data, list):
                    # List format - check if items are objects or just IDs
                    if comprehensive_data and isinstance(comprehensive_data[0], dict):
                        # List of model objects
                        models_data = [(item.get('name', f'model_{i}'), item) for i, item in enumerate(comprehensive_data)]
                    else:
                        # List of IDs (like lora.json) - skip this file
                        print(f"Skipping {catalog_file} - contains only IDs, not model objects")
                        continue
                else:
                    print(f"Unknown data format in {catalog_file}")
                    continue
                
                for model_id, model_info in models_data:
                    # Skip if model_info is not a dict (shouldn't happen but safety check)
                    if not isinstance(model_info, dict):
                        continue
                    
                    # Include all models regardless of availability status
                    # The UI will handle compatibility checks
                    
                    # Convert to simple format
                    simple_model = {
                        'type': 'checkpoints',
                        'description': model_info.get('description', ''),
                        'size_mb': model_info.get('size_on_disk_bytes', 0) // (1024 * 1024) if model_info.get('size_on_disk_bytes') else 0,
                        'dependencies': [],
                        'style': model_info.get('style', 'generalist'),
                        'baseline': model_info.get('baseline', 'stable_diffusion'),
                        'version': model_info.get('version', '1.0'),
                        'nsfw': model_info.get('nsfw', False),
                        'inpainting': model_info.get('inpainting', False)
                    }
                    
                    # Extract download URL
                    if 'config' in model_info and 'download' in model_info['config']:
                        downloads = model_info['config']['download']
                        if downloads and len(downloads) > 0:
                            simple_model['url'] = downloads[0]['file_url']
                            simple_model['filename'] = downloads[0]['file_name']
                    
                    # Add to simple catalog
                    simple_catalog[model_id] = simple_model
        
        # Write simple catalog
        output_path = Path(repo_path).parent / 'comfy-bridge' / 'model_configs.json'
        with open(output_path, 'w') as f:
            json.dump(simple_catalog, f, indent=2)
        
        print(f"Converted {len(simple_catalog)} models to simple catalog format")
        return True
        
    except Exception as e:
        print(f"Error converting catalog: {e}")
        return False

def sync_catalog_from_url(catalog_url: str, catalog_file: str) -> bool:
    """Sync catalog from remote URL"""
    try:
        print(f"Downloading catalog from {catalog_url}")
        
        response = requests.get(catalog_url, timeout=30)
        response.raise_for_status()
        
        catalog_data = response.json()
        
        # Write to local file
        with open(catalog_file, 'w') as f:
            json.dump(catalog_data, f, indent=2)
        
        print(f"Catalog downloaded and saved to {catalog_file}")
        return True
        
    except Exception as e:
        print(f"Error downloading catalog: {e}")
        return False

def validate_catalog(catalog_file: str) -> bool:
    """Validate catalog file format"""
    try:
        with open(catalog_file, 'r') as f:
            catalog = json.load(f)
        
        if not isinstance(catalog, dict):
            print("Catalog must be a JSON object")
            return False
        
        # Check for required fields in each model
        for model_id, model_config in catalog.items():
            if not isinstance(model_config, dict):
                print(f"Model {model_id} must be an object")
                return False
            
            required_fields = ['name', 'type']
            for field in required_fields:
                if field not in model_config:
                    print(f"Model {model_id} missing required field: {field}")
                    return False
        
        print("Catalog validation passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in catalog: {e}")
        return False
    except Exception as e:
        print(f"Error validating catalog: {e}")
        return False

def sync_catalog() -> bool:
    """Main catalog sync function"""
    config = load_catalog_config()
    
    # Try git sync first
    if sync_catalog_from_git(config['repository_path']):
        catalog_file = Path(config['repository_path']) / config['catalog_file']
        if catalog_file.exists():
            return validate_catalog(str(catalog_file))
    
    # Fallback to URL sync if git fails
    catalog_url = os.environ.get('CATALOG_URL')
    if catalog_url:
        catalog_file = config['catalog_file']
        if sync_catalog_from_url(catalog_url, catalog_file):
            return validate_catalog(catalog_file)
    
    print("No catalog sync method available")
    return False

def run_periodic_sync():
    """Run catalog sync periodically"""
    config = load_catalog_config()
    
    if not config['auto_sync']:
        print("Auto-sync disabled")
        return
    
    print(f"Starting periodic catalog sync (interval: {config['sync_interval']}s)")
    
    while True:
        try:
            print(f"Syncing catalog at {time.ctime()}")
            if sync_catalog():
                print("Catalog sync successful")
            else:
                print("Catalog sync failed")
        except Exception as e:
            print(f"Catalog sync error: {e}")
        
        time.sleep(config['sync_interval'])

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='Sync model catalog')
    parser.add_argument('--once', action='store_true', help='Sync once and exit')
    parser.add_argument('--validate-only', action='store_true', help='Only validate existing catalog')
    
    args = parser.parse_args()
    
    if args.validate_only:
        config = load_catalog_config()
        catalog_file = Path(config['repository_path']) / config['catalog_file']
        if catalog_file.exists():
            success = validate_catalog(str(catalog_file))
        else:
            print(f"Catalog file not found: {catalog_file}")
            success = False
        
        sys.exit(0 if success else 1)
    
    if args.once:
        success = sync_catalog()
        sys.exit(0 if success else 1)
    
    # Run periodic sync
    run_periodic_sync()

if __name__ == '__main__':
    main()
