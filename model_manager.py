#!/usr/bin/env python3
"""
Model Manager Script for ComfyUI Bridge
Manages model installation, hosting, and configuration
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Any, Optional
from pathlib import Path

def load_model_configs(config_path: str = 'model_configs.json') -> Dict[str, Any]:
    """Load model configurations from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {config_path} not found")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing {config_path}: {e}")
        return {}

def get_installed_models(models_path: str) -> Dict[str, bool]:
    """Check which models are installed"""
    installed = {}
    models_dir = Path(models_path)
    
    if not models_dir.exists():
        return installed
    
    # Check different model types
    model_types = ['checkpoints', 'diffusion_models', 'unet', 'vae', 'clip', 'text_encoders', 'loras']
    
    for model_type in model_types:
        type_dir = models_dir / model_type
        if type_dir.exists():
            for model_file in type_dir.iterdir():
                if model_file.is_file() and model_file.suffix in ['.safetensors', '.ckpt', '.pt', '.pth']:
                    installed[model_file.stem] = True
    
    return installed

def get_hosted_models() -> List[str]:
    """Get list of currently hosted models from environment or config"""
    hosted = os.environ.get('GRID_MODEL', '')
    if hosted:
        return [model.strip() for model in hosted.split(',') if model.strip()]
    return []

def set_hosted_models(models: List[str], env_file: str = '.env') -> bool:
    """Set hosted models in environment file"""
    try:
        # Read existing .env file
        env_content = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_content[key] = value
        
        # Update GRID_MODEL
        env_content['GRID_MODEL'] = ','.join(models) if models else ''
        
        # Write back to .env file
        with open(env_file, 'w') as f:
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")
        
        return True
    except Exception as e:
        print(f"Error updating {env_file}: {e}")
        return False

def list_models(config_path: str = 'model_configs.json', models_path: str = '/app/ComfyUI/models') -> Dict[str, Any]:
    """List all available models with their status"""
    configs = load_model_configs(config_path)
    installed = get_installed_models(models_path)
    hosted = get_hosted_models()
    
    result = {
        'models': {},
        'installed_count': len(installed),
        'hosted_count': len(hosted),
        'total_count': len(configs)
    }
    
    for model_id, config in configs.items():
        result['models'][model_id] = {
            **config,
            'installed': model_id in installed,
            'hosted': model_id in hosted
        }
    
    return result

def host_models(model_ids: List[str], env_file: str = '.env') -> bool:
    """Start hosting specified models"""
    return set_hosted_models(model_ids, env_file)

def unhost_models(model_ids: List[str], env_file: str = '.env') -> bool:
    """Stop hosting specified models"""
    hosted = get_hosted_models()
    remaining = [model for model in hosted if model not in model_ids]
    return set_hosted_models(remaining, env_file)

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='ComfyUI Bridge Model Manager')
    parser.add_argument('--action', choices=['list', 'host', 'unhost'], default='list',
                       help='Action to perform')
    parser.add_argument('--models', nargs='+', help='Model IDs for host/unhost actions')
    parser.add_argument('--config', default='model_configs.json', help='Model config file path')
    parser.add_argument('--models-path', default='/app/ComfyUI/models', help='Models directory path')
    parser.add_argument('--env-file', default='.env', help='Environment file path')
    
    args = parser.parse_args()
    
    if args.action == 'list':
        result = list_models(args.config, args.models_path)
        print(json.dumps(result, indent=2))
    
    elif args.action == 'host':
        if not args.models:
            print("Error: --models required for host action")
            sys.exit(1)
        success = host_models(args.models, args.env_file)
        if success:
            print(f"Started hosting models: {', '.join(args.models)}")
        else:
            print("Failed to update hosted models")
            sys.exit(1)
    
    elif args.action == 'unhost':
        if not args.models:
            print("Error: --models required for unhost action")
            sys.exit(1)
        success = unhost_models(args.models, args.env_file)
        if success:
            print(f"Stopped hosting models: {', '.join(args.models)}")
        else:
            print("Failed to update hosted models")
            sys.exit(1)

if __name__ == '__main__':
    main()
