#!/usr/bin/env python3
"""
ComfyUI Bridge - Model Management Web UI
Allows users to select and download models based on their GPU capabilities
"""

from flask import Flask, render_template, jsonify, request
import json
import subprocess
import os
import sys
from pathlib import Path
import requests

app = Flask(__name__)

# Configuration
COMFY_BRIDGE_PATH = os.getenv('COMFY_BRIDGE_PATH', '/app/comfy-bridge')
MODEL_CONFIGS_PATH = os.path.join(COMFY_BRIDGE_PATH, 'model_configs.json')
ENV_FILE_PATH = os.path.join(COMFY_BRIDGE_PATH, '.env')
MODELS_PATH = os.getenv('MODELS_PATH', '/app/ComfyUI/models')

def get_gpu_info():
    """Detect GPU information"""
    try:
        # Try to get NVIDIA GPU info
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            gpus = []
            for line in lines:
                parts = line.split(',')
                if len(parts) == 2:
                    name = parts[0].strip()
                    memory_str = parts[1].strip()
                    # Parse memory (e.g., "24576 MiB" -> 24576)
                    memory_mb = int(memory_str.split()[0])
                    gpus.append({
                        'name': name,
                        'memory_mb': memory_mb,
                        'memory_gb': round(memory_mb / 1024, 1)
                    })
            return {
                'available': True,
                'gpus': gpus,
                'total_memory_gb': sum(gpu['memory_gb'] for gpu in gpus)
            }
    except Exception as e:
        print(f"GPU detection failed: {e}", file=sys.stderr)
    
    # No GPU or detection failed
    return {
        'available': False,
        'gpus': [],
        'total_memory_gb': 0
    }

def load_model_configs():
    """Load model configurations from JSON"""
    try:
        with open(MODEL_CONFIGS_PATH, 'r') as f:
            configs = json.load(f)
        
        # Enhance with size estimates and requirements
        enhanced = {}
        for model_name, config in configs.items():
            size_gb = config.get('size', 0) / (1024**3) if config.get('size') else 0
            
            # Add dependency sizes
            dep_size_gb = 0
            if 'dependencies' in config:
                for dep in config['dependencies']:
                    dep_size_gb += dep.get('size', 0) / (1024**3) if dep.get('size') else 0
            
            total_size_gb = size_gb + dep_size_gb
            
            # Estimate VRAM requirements
            vram_required = estimate_vram_requirement(model_name, total_size_gb)
            
            enhanced[model_name] = {
                **config,
                'display_name': model_name,
                'size_gb': round(total_size_gb, 2),
                'vram_required_gb': vram_required,
                'category': categorize_model(model_name),
                'description': generate_description(model_name)
            }
        
        return enhanced
    except Exception as e:
        print(f"Error loading model configs: {e}", file=sys.stderr)
        return {}

def estimate_vram_requirement(model_name, size_gb):
    """Estimate VRAM requirement based on model name and size"""
    model_lower = model_name.lower()
    
    if 'flux' in model_lower:
        return 12  # Flux models typically need 12GB+
    elif 'sdxl' in model_lower:
        return 8   # SDXL needs ~8GB
    elif 'xl' in model_lower:
        return 8
    elif 'sd3' in model_lower:
        return 10
    elif size_gb > 10:
        return 12
    elif size_gb > 5:
        return 8
    else:
        return 6   # SD 1.5 and smaller

def categorize_model(model_name):
    """Categorize model by type"""
    model_lower = model_name.lower()
    
    if 'flux' in model_lower:
        return 'Flux'
    elif 'sdxl' in model_lower or 'xl' in model_lower:
        return 'Stable Diffusion XL'
    elif 'sd3' in model_lower:
        return 'Stable Diffusion 3'
    elif 'turbo' in model_lower:
        return 'Turbo'
    else:
        return 'Stable Diffusion'

def generate_description(model_name):
    """Generate a description for the model"""
    descriptions = {
        'Flux.1-Krea-dev Uncensored (fp8+CLIP+VAE)': 'Advanced Flux model with CLIP and VAE. High quality, uncensored outputs.',
        'sdxl': 'Stable Diffusion XL base model. High resolution, versatile.',
        'stable_diffusion': 'Classic Stable Diffusion 1.5. Fast, reliable, lower VRAM.',
    }
    return descriptions.get(model_name, f'{model_name} model for image generation')

def get_installed_models():
    """Get list of currently installed models"""
    installed = []
    models_path = Path(MODELS_PATH)
    
    if not models_path.exists():
        return []
    
    # Check for model files in checkpoints directory
    checkpoints_path = models_path / 'checkpoints'
    if checkpoints_path.exists():
        for model_file in checkpoints_path.glob('*.safetensors'):
            installed.append(model_file.stem)
    
    return installed

def get_selected_models():
    """Get models selected in .env file"""
    try:
        if not os.path.exists(ENV_FILE_PATH):
            return []
        
        with open(ENV_FILE_PATH, 'r') as f:
            for line in f:
                if line.startswith('GRID_MODEL='):
                    value = line.split('=', 1)[1].strip()
                    # Remove comments
                    value = value.split('#')[0].strip()
                    if value and value != '':
                        return [m.strip() for m in value.split(',')]
        return []
    except Exception as e:
        print(f"Error reading .env: {e}", file=sys.stderr)
        return []

def update_env_file(selected_models):
    """Update .env file with selected models"""
    try:
        # Read current .env
        lines = []
        if os.path.exists(ENV_FILE_PATH):
            with open(ENV_FILE_PATH, 'r') as f:
                lines = f.readlines()
        
        # Update GRID_MODEL line - remove ALL existing GRID_MODEL lines first
        model_value = ','.join(selected_models) if selected_models else ''
        new_lines = []
        grid_model_found = False
        preserved_comment = ''
        
        for line in lines:
            if line.startswith('GRID_MODEL='):
                # Skip this line (remove it) but preserve comment from first occurrence
                if not grid_model_found and '#' in line:
                    preserved_comment = '  #' + line.split('#', 1)[1].rstrip()
                grid_model_found = True
                continue  # Skip adding this line
            new_lines.append(line)
        
        # Add the single GRID_MODEL line at the correct position
        # Find where to insert (after GRID_MAX_PIXELS or at the end of config section)
        insert_index = -1
        for i, line in enumerate(new_lines):
            if line.startswith('GRID_MAX_PIXELS='):
                insert_index = i + 1
                break
        
        # Create the new GRID_MODEL line
        if preserved_comment:
            new_model_line = f'GRID_MODEL={model_value}{preserved_comment}\n'
        else:
            new_model_line = f'GRID_MODEL={model_value}\n'
        
        # Insert at the appropriate position
        if insert_index > 0:
            new_lines.insert(insert_index, new_model_line)
        else:
            new_lines.append(new_model_line)
        
        # Write back
        with open(ENV_FILE_PATH, 'w') as f:
            f.writelines(new_lines)
        
        return True
    except Exception as e:
        print(f"Error updating .env: {e}", file=sys.stderr)
        return False

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/gpu-info')
def api_gpu_info():
    """Get GPU information"""
    return jsonify(get_gpu_info())

@app.route('/api/models')
def api_models():
    """Get available models with metadata"""
    models = load_model_configs()
    installed = get_installed_models()
    selected = get_selected_models()
    
    # Add installation status to each model
    for model_name in models:
        models[model_name]['installed'] = model_name in installed
        models[model_name]['selected'] = model_name in selected
    
    return jsonify(models)

@app.route('/api/models/selected', methods=['GET', 'POST'])
def api_selected_models():
    """Get or update selected models"""
    if request.method == 'GET':
        return jsonify({'models': get_selected_models()})
    
    elif request.method == 'POST':
        data = request.json
        selected = data.get('models', [])
        
        if update_env_file(selected):
            return jsonify({'success': True, 'message': 'Models updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update models'}), 500

@app.route('/api/models/download', methods=['POST'])
def api_download_models():
    """Trigger model download"""
    try:
        # Run download_models.py script
        result = subprocess.run(
            ['python3', 'download_models.py'],
            cwd=COMFY_BRIDGE_PATH,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Download timeout (1 hour exceeded)'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/disk-space')
def api_disk_space():
    """Get disk space information"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(MODELS_PATH)
        return jsonify({
            'total_gb': round(total / (1024**3), 2),
            'used_gb': round(used / (1024**3), 2),
            'free_gb': round(free / (1024**3), 2),
            'percent_used': round(used / total * 100, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Ensure .env file exists
    if not os.path.exists(ENV_FILE_PATH):
        print(f"Warning: .env file not found at {ENV_FILE_PATH}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)

