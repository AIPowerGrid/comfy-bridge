#!/usr/bin/env python3
"""
Test script for Z-Image-Turbo workflow via ComfyUI API.
Tests that prompt and seed are properly passed.
"""

import json
import requests
import time
import sys

COMFY_URL = "http://127.0.0.1:8188"

def load_workflow():
    """Load the Z-Image-Turbo API workflow."""
    with open("workflows/image_z_image_turbo_api.json", "r") as f:
        return json.load(f)

def update_workflow_with_params(workflow, prompt, seed=None):
    """Update workflow with prompt and seed - simulating bridge logic."""
    import random
    
    # Generate random seed if not provided
    if seed is None:
        seed = random.randint(1, 2**32-1)
    
    # Update PrimitiveStringMultiline nodes (Z-Image-Turbo style)
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
            
        class_type = node.get("class_type", "")
        
        # Handle PrimitiveStringMultiline - this is where prompt goes in Z-Image-Turbo
        if class_type == "PrimitiveStringMultiline":
            if "inputs" not in node:
                node["inputs"] = {}
            node["inputs"]["value"] = prompt
            print(f"✓ Set prompt in PrimitiveStringMultiline node {node_id}")
        
        # Handle KSampler - this is where seed goes
        elif class_type == "KSampler":
            if "inputs" in node:
                node["inputs"]["seed"] = seed
                print(f"✓ Set seed={seed} in KSampler node {node_id}")
        
        # Handle SaveImage - update filename prefix
        elif class_type == "SaveImage":
            if "inputs" in node:
                node["inputs"]["filename_prefix"] = "zimage_test"
                print(f"✓ Set filename_prefix in SaveImage node {node_id}")
    
    return workflow

def queue_prompt(workflow):
    """Queue a prompt to ComfyUI."""
    payload = {"prompt": workflow}
    
    print(f"\nSubmitting workflow to {COMFY_URL}/prompt...")
    response = requests.post(f"{COMFY_URL}/prompt", json=payload)
    
    if response.status_code != 200:
        print(f"✗ Error: {response.status_code} - {response.text}")
        return None
    
    result = response.json()
    prompt_id = result.get("prompt_id")
    print(f"✓ Workflow queued with prompt_id: {prompt_id}")
    return prompt_id

def wait_for_completion(prompt_id, timeout=120):
    """Wait for the generation to complete."""
    print(f"\nWaiting for generation (timeout: {timeout}s)...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}")
        if response.status_code != 200:
            print(f"  Error checking status: {response.status_code}")
            time.sleep(2)
            continue
        
        history = response.json()
        
        if prompt_id in history:
            entry = history[prompt_id]
            
            # Check for error
            if "error" in entry:
                print(f"✗ Generation failed: {entry['error']}")
                return None
            
            # Check for outputs
            if entry.get("outputs"):
                print(f"✓ Generation completed!")
                return entry
        
        elapsed = int(time.time() - start_time)
        print(f"  Waiting... ({elapsed}s)", end="\r")
        time.sleep(1)
    
    print(f"\n✗ Timeout after {timeout}s")
    return None

def get_image_info(result):
    """Extract image info from result."""
    for node_id, output in result.get("outputs", {}).items():
        if "images" in output:
            for img in output["images"]:
                print(f"✓ Generated image: {img['filename']}")
                print(f"  Type: {img.get('type', 'output')}")
                print(f"  Subfolder: {img.get('subfolder', '')}")
                return img
    return None

def main():
    # Test parameters
    test_prompt = "A majestic red dragon flying over a medieval castle at sunset, epic fantasy art, detailed scales, dramatic lighting"
    test_seed = 42
    
    print("=" * 60)
    print("Z-Image-Turbo Workflow Test")
    print("=" * 60)
    print(f"\nTest prompt: {test_prompt[:60]}...")
    print(f"Test seed: {test_seed}")
    print()
    
    # Load workflow
    print("Loading workflow...")
    try:
        workflow = load_workflow()
        print(f"✓ Loaded workflow with {len(workflow)} nodes")
    except FileNotFoundError:
        print("✗ Workflow file not found: workflows/image_z_image_turbo_api.json")
        sys.exit(1)
    
    # Show workflow structure
    print("\nWorkflow structure:")
    for node_id, node in workflow.items():
        if isinstance(node, dict):
            class_type = node.get("class_type", "unknown")
            print(f"  {node_id}: {class_type}")
    
    # Update workflow with test parameters
    print("\nUpdating workflow with test parameters...")
    workflow = update_workflow_with_params(workflow, test_prompt, test_seed)
    
    # Queue the prompt
    prompt_id = queue_prompt(workflow)
    if not prompt_id:
        sys.exit(1)
    
    # Wait for completion
    result = wait_for_completion(prompt_id)
    if not result:
        sys.exit(1)
    
    # Get image info
    print("\nResult:")
    img_info = get_image_info(result)
    
    if img_info:
        print(f"\n✓ SUCCESS! Image available at:")
        print(f"  {COMFY_URL}/view?filename={img_info['filename']}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
