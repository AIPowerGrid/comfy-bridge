#!/usr/bin/env python3
"""
ComfyUI Bridge Startup Script

This script provides a convenient way to start the ComfyUI Bridge with 
enhanced logging and error handling.
"""

import asyncio
import logging
import sys
from pathlib import Path

def setup_logging():
    """Set up enhanced logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bridge.log')
        ]
    )
    
    # Reduce httpx logging noise
    logging.getLogger("httpx").setLevel(logging.WARNING)

def check_prerequisites():
    """Check if basic requirements are met"""
    print("🔍 Checking prerequisites...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Copy env.example to .env and configure your settings")
        print("   You can also run 'python check_config.py' for detailed diagnostics")
        return False
    
    # Check if workflows directory exists
    workflows_dir = Path("workflows")
    if not workflows_dir.exists():
        print("❌ workflows/ directory not found!")
        return False
    
    print("✅ Basic prerequisites met")
    return True

async def main():
    """Main entry point"""
    print("🚀 Starting ComfyUI Bridge...")
    print("=" * 50)
    
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above.")
        print("   Run 'python check_config.py' for detailed diagnostics.")
        sys.exit(1)
    
    setup_logging()
    
    try:
        from comfy_bridge.cli import main as cli_main
        await cli_main()
    except ImportError:
        print("❌ ComfyUI Bridge not installed!")
        print("   Run 'pip install -e .' to install in development mode")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped by user")
        sys.exit(0)
