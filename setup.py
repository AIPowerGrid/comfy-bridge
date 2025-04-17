#!/usr/bin/env python3
"""Setup script for ComfyUI bridge.

This script helps set up the required dependencies and configuration
for running the ComfyUI bridge for AI Horde.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Set up ComfyUI bridge for AI Horde")
    parser.add_argument(
        "--comfyui-path", 
        type=str, 
        help="Path to ComfyUI installation. If not provided, will install ComfyUI."
    )
    parser.add_argument(
        "--api-key", 
        type=str, 
        help="AI Horde API key. If not provided, will prompt for it."
    )
    parser.add_argument(
        "--worker-name", 
        type=str, 
        default="ComfyUI-Bridge-Worker",
        help="Worker name to use for the AI Horde."
    )
    parser.add_argument(
        "--nsfw", 
        action="store_true", 
        help="Allow NSFW content"
    )
    parser.add_argument(
        "--threads", 
        type=int, 
        default=1,
        help="Number of concurrent jobs to process"
    )
    return parser.parse_args()

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import httpx
        import requests
        import PIL
        print("✅ Basic dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        return False

def install_dependencies():
    """Install required dependencies."""
    print("Installing dependencies...")
    requirements = [
        "httpx>=0.24.0",
        "requests>=2.28.0",
        "pillow>=9.0.0",
    ]
    
    subprocess.check_call([sys.executable, "-m", "pip", "install", *requirements])
    print("✅ Dependencies installed")

def setup_comfyui(comfyui_path=None):
    """Set up ComfyUI if not already installed."""
    if comfyui_path and os.path.exists(comfyui_path):
        print(f"✅ Using existing ComfyUI installation at {comfyui_path}")
        return comfyui_path
    
    # Default install location
    install_dir = Path.home() / "ComfyUI"
    
    if os.path.exists(install_dir):
        print(f"✅ ComfyUI already installed at {install_dir}")
        return str(install_dir)
    
    print("ComfyUI not found. Cloning repository...")
    subprocess.check_call(["git", "clone", "https://github.com/comfyanonymous/ComfyUI.git", str(install_dir)])
    
    # Install ComfyUI dependencies
    print("Installing ComfyUI dependencies...")
    os.chdir(install_dir)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    print(f"✅ ComfyUI installed at {install_dir}")
    return str(install_dir)

def create_env_file(api_key, worker_name, comfyui_path, nsfw=False, threads=1):
    """Create .env file with configuration."""
    env_file = Path(__file__).parent / ".env"
    
    with open(env_file, "w") as f:
        f.write(f"HORDE_API_KEY={api_key}\n")
        f.write(f"HORDE_WORKER_NAME={worker_name}\n")
        f.write(f"COMFYUI_PATH={comfyui_path}\n")
        f.write(f"COMFYUI_URL=http://127.0.0.1:8188\n")
        f.write(f"HORDE_NSFW={'true' if nsfw else 'false'}\n")
        f.write(f"HORDE_THREADS={threads}\n")
        f.write(f"HORDE_MAX_PIXELS=1048576\n")  # 1024x1024
    
    print(f"✅ Configuration saved to {env_file}")

def setup_launcher():
    """Create launcher scripts."""
    bridge_dir = Path(__file__).parent
    
    # Create run.py
    run_script = bridge_dir / "run.py"
    with open(run_script, "w") as f:
        f.write("""#!/usr/bin/env python3
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Load environment variables
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

# Start ComfyUI in the background
comfyui_path = os.environ.get("COMFYUI_PATH")
if not comfyui_path:
    print("Error: COMFYUI_PATH not set in .env file")
    sys.exit(1)

print(f"Starting ComfyUI from {comfyui_path}...")
comfyui_process = subprocess.Popen(
    [sys.executable, "main.py", "--listen", "0.0.0.0"], 
    cwd=comfyui_path,
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT
)

# Wait for ComfyUI to start
print("Waiting for ComfyUI to start...")
time.sleep(5)

# Run the bridge
print("Starting ComfyUI bridge...")
from bridge import main
asyncio.run(main())
""")
    
    os.chmod(run_script, 0o755)
    print(f"✅ Created launcher script at {run_script}")

def main():
    """Main setup function."""
    args = parse_args()
    
    print("Setting up ComfyUI bridge for AI Horde...")
    
    # Check and install dependencies
    if not check_dependencies():
        install_dependencies()
    
    # Set up ComfyUI
    comfyui_path = setup_comfyui(args.comfyui_path)
    
    # Get API key if not provided
    api_key = args.api_key
    if not api_key:
        api_key = input("Enter your AI Horde API key: ")
    
    # Create .env file
    create_env_file(
        api_key=api_key,
        worker_name=args.worker_name,
        comfyui_path=comfyui_path,
        nsfw=args.nsfw,
        threads=args.threads,
    )
    
    # Setup launcher scripts
    setup_launcher()
    
    print("\n✅ Setup complete!")
    print("To start the bridge, run:")
    print(f"  python {Path(__file__).parent}/run.py")
    print("\nMake sure you have models installed in ComfyUI before starting.")

if __name__ == "__main__":
    main() 