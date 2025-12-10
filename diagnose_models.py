#!/usr/bin/env python3
"""Diagnostic script to check model detection."""

import os
import sys
from pathlib import Path

# Add comfy_bridge to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Output to both console and file
output_file = Path(__file__).parent / "diagnose_output.txt"
out_f = open(output_file, "w", encoding="utf-8")

def log(msg):
    print(msg)
    out_f.write(msg + "\n")
    out_f.flush()

def main():
    log("=" * 60)
    log("COMFY-BRIDGE MODEL DIAGNOSTIC")
    log("=" * 60)
    
    # 1. Check environment variables
    log(f"\n[1] Environment Variables:")
    models_path = os.environ.get("MODELS_PATH", "NOT SET")
    log(f"    MODELS_PATH: {models_path}")
    ref_path = os.environ.get("GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH", "NOT SET")
    log(f"    GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH: {ref_path}")
    workflow_file = os.environ.get("WORKFLOW_FILE", "NOT SET")
    log(f"    WORKFLOW_FILE: {workflow_file}")
    
    if models_path != "NOT SET":
        p = Path(models_path)
        log(f"    Models path exists: {p.exists()}")
        if p.exists():
            subdirs = [d.name for d in p.iterdir() if d.is_dir()]
            log(f"    Subdirectories: {subdirs}")
    
    if ref_path != "NOT SET":
        catalog_file = Path(ref_path) / "stable_diffusion.json"
        log(f"    Catalog file exists: {catalog_file.exists()}")
    
    # 2. List ALL model files found
    log(f"\n[2] All Model Files Found:")
    try:
        from comfy_bridge.health import get_health_checker
        checker = get_health_checker()
        log(f"    Models path: {checker.models_path}")
        
        all_files = checker.list_all_model_files()
        total = 0
        for dir_name, files in sorted(all_files.items()):
            log(f"    {dir_name}/:")
            for f in files:
                log(f"      - {f}")
                total += 1
        log(f"    Total files found: {total}")
    except Exception as e:
        import traceback
        log(f"    Error: {e}")
        log(traceback.format_exc())
    
    # 3. Check advertised models from WORKFLOW_FILE
    log(f"\n[3] Advertised Models Health Check:")
    if workflow_file != "NOT SET":
        models = [m.strip() for m in workflow_file.split(",") if m.strip()]
        log(f"    Models to check: {models}")
        
        try:
            from comfy_bridge.health import get_health_checker
            checker = get_health_checker()
            
            for model_name in models:
                health = checker.check_model_by_name(model_name)
                status_icon = "OK" if health.status.value == "healthy" else "FAIL"
                log(f"\n    [{status_icon}] {model_name}:")
                log(f"        Status: {health.status.value}")
                if health.present_files:
                    log(f"        Found: {health.present_files}")
                if health.missing_files:
                    log(f"        Missing: {health.missing_files}")
                if health.error_message:
                    log(f"        Message: {health.error_message}")
        except Exception as e:
            import traceback
            log(f"    Error: {e}")
            log(traceback.format_exc())
    
    # 4. Check workflow mapping (with async initialization like bridge.py)
    log(f"\n[4] Workflow Mapping:")
    try:
        import asyncio
        from comfy_bridge.model_mapper import model_mapper, initialize_model_mapper
        from comfy_bridge.config import Settings
        
        # Initialize like the bridge does
        async def init_mapper():
            await initialize_model_mapper(Settings.COMFYUI_URL)
        
        asyncio.run(init_mapper())
        
        available = model_mapper.get_available_horde_models()
        log(f"    Available models ({len(available)}): {available}")
        
        # Check specific mappings
        if workflow_file != "NOT SET":
            models = [m.strip() for m in workflow_file.split(",") if m.strip()]
            for model_name in models:
                workflow = model_mapper.get_workflow_file(model_name)
                log(f"    {model_name} -> {workflow}")
    except Exception as e:
        import traceback
        log(f"    Error: {e}")
        log(traceback.format_exc())
    
    # 5. Check ModelVault registry
    log(f"\n[5] ModelVault Registry:")
    try:
        from comfy_bridge.modelvault_client import get_modelvault_client
        client = get_modelvault_client()
        
        # Check if catalog is being loaded
        all_models = client.fetch_all_models()
        log(f"    Total models in registry: {len(all_models)}")
        
        # Show first 10 models with their files
        log(f"    Sample models:")
        for i, (name, model) in enumerate(list(all_models.items())[:10]):
            file_count = len(model.files) if model.files else 0
            log(f"      - {name}: {file_count} files")
            if model.files:
                for f in model.files[:3]:
                    log(f"          {f.file_name} (type={f.file_type})")
                if len(model.files) > 3:
                    log(f"          ... and {len(model.files) - 3} more")
    except Exception as e:
        import traceback
        log(f"    Error: {e}")
        log(traceback.format_exc())
    
    log("\n" + "=" * 60)
    log("END DIAGNOSTIC")
    log("=" * 60)
    
    out_f.close()
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    main()
