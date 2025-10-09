#!/usr/bin/env python3
"""
Simple script to get GPU information and output as JSON.
Can be called by the management UI to get real GPU data.
"""
import json
import subprocess
import sys

def get_gpu_info():
    """Get GPU information using nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        if not result.stdout.strip():
            return {"available": False, "gpus": [], "total_memory_gb": 0}
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                name = parts[0]
                memory_str = parts[1]
                # Parse memory (e.g., "98304 MiB" -> 98304)
                memory_mb = int(memory_str.split()[0])
                memory_gb = round(memory_mb / 1024, 1)
                gpus.append({
                    "name": name,
                    "memory_mb": memory_mb,
                    "memory_gb": memory_gb
                })
        
        total_memory_gb = round(sum(gpu["memory_gb"] for gpu in gpus), 1)
        
        return {
            "available": True,
            "gpus": gpus,
            "total_memory_gb": total_memory_gb
        }
    
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"available": False, "gpus": [], "total_memory_gb": 0, "error": str(e)}

if __name__ == '__main__':
    gpu_info = get_gpu_info()
    print(json.dumps(gpu_info, indent=2))

