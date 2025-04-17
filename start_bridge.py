#!/usr/bin/env python3
"""
Start script for the ComfyUI Bridge for AI Power Grid.

This script loads environment variables from a .env file and starts the bridge.
"""

import os
import sys
import logging
import asyncio
import argparse
import signal
from dotenv import load_dotenv

# Import the bridge module
from bridge import ComfyUIBridge

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for shutdown handling
bridge = None
shutdown_event = None

def print_header():
    """Print a banner for the ComfyUI Bridge."""
    print("\n" + "=" * 80)
    print(" " * 25 + "ComfyUI Bridge for AI Power Grid")
    print("=" * 80)
    print("This bridge connects your local ComfyUI installation to the AI Power Grid,")
    print("allowing it to work as an image worker for the distributed network.")
    print("=" * 80 + "\n")

def handle_shutdown(sig, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_event
    
    if shutdown_event is None:
        return
        
    logger.info("Shutdown signal received. Gracefully stopping worker...")
    shutdown_event.set()

async def main():
    """Main entry point for the bridge."""
    global bridge, shutdown_event
    
    # Create shutdown event for graceful termination
    shutdown_event = asyncio.Event()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start ComfyUI bridge')
    parser.add_argument('--workflow', '-w', help='Workflow JSON file to use from workflows directory')
    parser.add_argument('--grid-model', help='Model to advertise to the grid (overrides GRID_MODEL in .env)')
    args = parser.parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get configuration from environment variables or use defaults
    api_key = os.environ.get("GRID_API_KEY", "")
    worker_name = os.environ.get("GRID_WORKER_NAME", "ComfyUI-Bridge-Worker")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8000")  # Default to port 8000
    nsfw = os.environ.get("GRID_NSFW", "false").lower() == "true"
    threads = int(os.environ.get("GRID_THREADS", "1"))
    max_pixels = int(os.environ.get("GRID_MAX_PIXELS", "1048576"))
    api_url = os.environ.get("GRID_API_URL", "https://api.aipowergrid.io/api")
    workflow_dir = os.environ.get("WORKFLOW_DIR", os.path.join(os.getcwd(), "workflows"))
    
    # Use command line argument for workflow file if provided, otherwise use environment variable
    workflow_file = args.workflow or os.environ.get("WORKFLOW_FILE")
    
    # Use command line argument for grid model if provided, otherwise use environment variable
    grid_model = args.grid_model or os.environ.get("GRID_MODEL")
    
    if not api_key:
        print("Error: GRID_API_KEY environment variable is required")
        sys.exit(1)
    
    if workflow_file:
        print(f"Using workflow file: {workflow_file}")
    else:
        print("No workflow file specified. Using default workflow.")
        
    if grid_model:
        print(f"Advertising model to grid: {grid_model}")
    
    print_header()
    
    print("Starting bridge with the following configuration:")
    print(f"- Worker name: {worker_name}")
    print(f"- ComfyUI URL: {comfy_url}")
    print(f"- API URL: {api_url}")
    print(f"- NSFW allowed: {nsfw}")
    print(f"- Concurrent threads: {threads}")
    print(f"- Max pixels: {max_pixels}\n")
    
    try:
        # Create and start the bridge
        bridge = ComfyUIBridge(
            api_key=api_key,
            worker_name=worker_name,
            base_url=api_url,
            comfy_url=comfy_url,
            nsfw=nsfw,
            threads=threads,
            max_pixels=max_pixels,
            workflow_dir=workflow_dir,
            workflow_file=workflow_file,
            grid_model=grid_model
        )
        
        # Start the bridge
        bridge_task = asyncio.create_task(bridge.start())
        
        # Wait for either bridge to complete or shutdown event
        await asyncio.wait(
            [bridge_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If we're here because of shutdown event, ensure worker is properly shut down
        if shutdown_event.is_set() and bridge.running:
            logger.info("Gracefully shutting down worker...")
            await bridge._unregister_worker()
            await bridge._cleanup()
            logger.info("Worker gracefully stopped. Note: It may still appear online in the AI Power Grid for a while.")
    except Exception as e:
        logger.error(f"Error starting bridge: {e}")
    finally:
        # Ensure we clean up resources
        if bridge:
            await bridge._cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 