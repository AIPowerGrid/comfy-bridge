#!/usr/bin/env python3
"""
GPU Information Script for ComfyUI Bridge
Provides GPU detection and information for the management UI
"""

import json
import subprocess
import sys
import os
from typing import Dict, List, Any

def get_nvidia_gpu_info() -> Dict[str, Any]:
    """Get NVIDIA GPU information using nvidia-smi"""
    try:
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=index,name,memory.total,memory.free,memory.used,temperature.gpu,utilization.gpu',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, check=True)
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 7:
                    gpus.append({
                        'index': int(parts[0]),
                        'name': parts[1],
                        'memory_total_mb': int(parts[2]),
                        'memory_free_mb': int(parts[3]),
                        'memory_used_mb': int(parts[4]),
                        'temperature_c': int(parts[5]) if parts[5] != 'N/A' else None,
                        'utilization_percent': int(parts[6]) if parts[6] != 'N/A' else None,
                        'memory_gb': round(int(parts[2]) / 1024, 1),
                        'memory_free_gb': round(int(parts[3]) / 1024, 1),
                        'memory_used_gb': round(int(parts[4]) / 1024, 1)
                    })
        
        return {
            'available': True,
            'driver': 'nvidia',
            'gpus': gpus,
            'total_memory_gb': sum(gpu['memory_gb'] for gpu in gpus),
            'total_memory_free_gb': sum(gpu['memory_free_gb'] for gpu in gpus),
            'total_memory_used_gb': sum(gpu['memory_used_gb'] for gpu in gpus)
        }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return {'available': False, 'gpus': [], 'total_memory_gb': 0}

def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information as fallback"""
    try:
        # Get CPU count
        cpu_count = os.cpu_count() or 1
        
        # Try to get memory info
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        total_gb = round(total_kb / 1024 / 1024, 1)
                        break
                else:
                    total_gb = 8.0  # Default fallback
        except:
            total_gb = 8.0
        
        return {
            'available': True,
            'driver': 'cpu',
            'gpus': [{
                'index': 0,
                'name': 'CPU',
                'memory_gb': total_gb,
                'memory_free_gb': total_gb * 0.8,  # Estimate
                'memory_used_gb': total_gb * 0.2,   # Estimate
                'temperature_c': None,
                'utilization_percent': None
            }],
            'total_memory_gb': total_gb,
            'total_memory_free_gb': total_gb * 0.8,
            'total_memory_used_gb': total_gb * 0.2
        }
    except:
        return {'available': False, 'gpus': [], 'total_memory_gb': 0}

def main():
    """Main function to get GPU information"""
    # Try NVIDIA first
    gpu_info = get_nvidia_gpu_info()
    
    # Fallback to CPU if no GPU available
    if not gpu_info['available']:
        gpu_info = get_cpu_info()
    
    # Output as JSON
    print(json.dumps(gpu_info, indent=2))

if __name__ == '__main__':
    main()
