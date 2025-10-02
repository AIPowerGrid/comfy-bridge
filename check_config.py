#!/usr/bin/env python3
"""
ComfyUI Bridge Configuration Checker

This script helps diagnose common configuration issues with the ComfyUI Bridge.
Run this script before starting the bridge to ensure everything is set up correctly.
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists and contains required settings"""
    print("🔍 Checking .env file...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Copy env.example to .env and configure your settings")
        return False
        
    # Read .env file
    with open(".env", "r") as f:
        env_content = f.read()
    
    # Check for required settings
    required_settings = [
        ("GRID_API_KEY", "your_api_key_here"),
    ]
    
    missing_settings = []
    for setting, default_value in required_settings:
        if setting not in env_content or default_value in env_content:
            missing_settings.append(setting)
    
    if missing_settings:
        print(f"❌ Missing or unconfigured settings in .env:")
        for setting in missing_settings:
            print(f"   - {setting}")
        return False
    
    print("✅ .env file looks good!")
    return True

def check_workflow_files():
    """Check if workflow files exist"""
    print("\n🔍 Checking workflow files...")
    
    workflows_dir = Path("workflows")
    if not workflows_dir.exists():
        print("❌ workflows/ directory not found!")
        return False
    
    # Check for video workflow files
    video_workflows = [
        "wan2.2-t2v-a14b.json",
        "wan2.2-t2v-a14b-hq.json", 
        "wan2.2_ti2v_5B.json"
    ]
    
    missing_workflows = []
    for workflow in video_workflows:
        if not (workflows_dir / workflow).exists():
            missing_workflows.append(workflow)
    
    if missing_workflows:
        print(f"⚠️  Missing {len(missing_workflows)} video workflow files:")
        for workflow in missing_workflows:
            print(f"   - {workflow}")
        print("   Video generation may not work for these models")
    else:
        print("✅ All video workflow files found!")
    
    return len(missing_workflows) == 0

def check_comfyui_connection():
    """Check if ComfyUI is accessible"""
    print("\n🔍 Checking ComfyUI connection...")
    
    try:
        import httpx
        
        # Try default ComfyUI URL
        comfyui_url = os.getenv("COMFYUI_URL", "http://localhost:8188")
        
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{comfyui_url}/system_stats")
            response.raise_for_status()
        
        print(f"✅ ComfyUI is accessible at {comfyui_url}")
        return True
    except ImportError:
        print("❌ httpx not installed (pip install httpx)")
        return False
    except Exception as e:
        print(f"❌ Cannot connect to ComfyUI at {comfyui_url}")
        print(f"   Error: {e}")
        print("   Make sure ComfyUI is running and accessible")
        return False

def check_api_key():
    """Check if API key is valid"""
    print("\n🔍 Checking AI Power Grid API key...")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GRID_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("❌ GRID_API_KEY not set or using default value")
        print("   Get your API key from https://aipowergrid.io")
        return False
    
    try:
        import httpx
        
        api_url = os.getenv("GRID_API_URL", "https://api.aipowergrid.io/api")
        
        with httpx.Client(timeout=10) as client:
            headers = {"apikey": api_key}
            response = client.get(f"{api_url}/v2/status/heartbeat", headers=headers)
            
            if response.status_code == 200:
                print("✅ API key is valid!")
                return True
            elif response.status_code == 401:
                print("❌ API key is invalid")
                return False
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                return False
                
    except ImportError:
        print("❌ httpx not installed (pip install httpx)")
        return False
    except Exception as e:
        print(f"❌ Cannot check API key: {e}")
        return False

def main():
    """Run all checks"""
    print("🚀 ComfyUI Bridge Configuration Checker")
    print("=" * 50)
    
    checks = [
        check_env_file,
        check_workflow_files, 
        check_comfyui_connection,
        check_api_key
    ]
    
    results = []
    for check in checks:
        results.append(check())
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print("🎉 All checks passed! Your bridge should work correctly.")
        print("   Run 'python -m comfy_bridge.cli' to start the bridge")
    else:
        print(f"❌ {total - passed} checks failed. Please fix the issues above.")
        print("   The bridge may not work correctly until these are resolved.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
