#!/usr/bin/env python3
"""
Test script for video generation with wan2.2_t2v model
"""

import os
import asyncio
import logging
from comfy_bridge.bridge import ComfyUIBridge
from comfy_bridge.config import Settings
from comfy_bridge.model_mapper import initialize_model_mapper

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_video_gen")

# Manual job definition that simulates what would come from the API
test_job = {
    "id": "test_video_job_1",
    "model": "wan2.2_t2v",
    "source_processing": "txt2img",
    "payload": {
        "prompt": "Beautiful young woman with long hair walking on a beach at sunset, cinematic lighting, slow motion, 4k",
        "negative_prompt": "Bright colors, overexposed, static, blurry details, worst quality, low quality, ugly",
        "width": 640,
        "height": 640,
        "seed": 1234567890,
        # Add special flag for video generation
        "video": True,
        "video_length": 81  # Same as in wan2_2_t2v_14b.json
    }
}

async def test_video_generation():
    """Test video generation using the wan2.2_t2v model"""
    Settings.validate()
    bridge = ComfyUIBridge()
    
    # Initialize model mapper
    await initialize_model_mapper(Settings.COMFYUI_URL)
    
    try:
        # Set up the bridge with the correct model
        bridge.supported_models = ["wan2.2_t2v"]
        logger.info(f"Supported models: {bridge.supported_models}")
        
        # Process the test job manually
        logger.info(f"Processing test job: {test_job}")
        
        # Build workflow with our test job
        from comfy_bridge.workflow import build_workflow
        wf = await build_workflow(test_job)
        
        # Send to ComfyUI
        logger.info(f"Sending workflow to ComfyUI")
        resp = await bridge.comfy.post("/prompt", json={"prompt": wf})
        resp.raise_for_status()
        prompt_id = resp.json().get("prompt_id")
        
        if not prompt_id:
            logger.error("No prompt_id received")
            return
            
        logger.info(f"Prompt ID: {prompt_id}")
        
        # Wait for result
        while True:
            logger.info("Checking generation status...")
            hist = await bridge.comfy.get(f"/history/{prompt_id}")
            hist.raise_for_status()
            data = hist.json().get(prompt_id, {})
            
            if not data:
                logger.info("No data yet, waiting...")
                await asyncio.sleep(2)
                continue
                
            outputs = data.get("outputs", {})
            if outputs:
                logger.info(f"Found outputs: {outputs}")
                node_id, node_data = next(iter(outputs.items()))
                
                # Handle videos
                videos = node_data.get("videos", [])
                if videos:
                    filename = videos[0]["filename"]
                    logger.info(f"Generated video: {filename}")
                    break
                
                # Handle images
                imgs = node_data.get("images", [])
                if imgs:
                    filename = imgs[0]["filename"]
                    logger.info(f"Generated image: {filename}")
                    break
            
            logger.info("Still processing, waiting...")
            await asyncio.sleep(2)
        
        logger.info("Generation completed successfully")
    
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Clean up
        await bridge.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(test_video_generation())
    except KeyboardInterrupt:
        print("Test interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
