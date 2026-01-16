#!/usr/bin/env python3
"""
Test the bridge's workflow update logic for Z-Image-Turbo.
This simulates what happens when a job comes in from the grid.
"""

import json
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bridge import ComfyUIBridge, DummyJobPopResponse

def test_bridge_logic():
    """Test the bridge's _update_workflow_with_job_params method."""
    
    print("=" * 60)
    print("Bridge Logic Test for Z-Image-Turbo")
    print("=" * 60)
    
    # Load the Z-Image-Turbo workflow
    workflow_path = "workflows/image_z_image_turbo_api.json"
    print(f"\nLoading workflow: {workflow_path}")
    
    with open(workflow_path, "r") as f:
        workflow_template = json.load(f)
    
    print(f"✓ Loaded {len(workflow_template)} nodes")
    
    # Create a mock bridge instance
    bridge = ComfyUIBridge(
        worker_name="test_worker",
        api_key="test_key",
        workflow_dir="workflows",
        workflow_file="image_z_image_turbo_api.json"
    )
    bridge.workflow_template = workflow_template
    
    # Create a mock job from the grid
    test_prompt = "A beautiful sunset over the ocean, golden hour lighting, photorealistic"
    test_negative = "blurry, low quality"  # Note: Z-Image doesn't use negative, but we test it doesn't break
    test_seed = 12345
    
    print(f"\nSimulating grid job:")
    print(f"  Prompt: {test_prompt[:50]}...")
    print(f"  Negative: {test_negative}")
    print(f"  Seed: {test_seed}")
    
    job_data = {
        "id": "test-job-123",
        "model": "z_image_turbo",
        "kudos": 10,
        "payload": {
            "prompt": test_prompt,
            "negative_prompt": test_negative,
            "seed": test_seed,
            "width": 1024,
            "height": 1024,
            "steps": 4,
            "cfg_scale": 1,
            "sampler_name": "res_multistep"
        }
    }
    
    job = DummyJobPopResponse(**job_data)
    
    # Run the bridge's workflow update logic
    print("\nRunning bridge._update_workflow_with_job_params()...")
    print("-" * 40)
    
    updated_workflow = bridge._update_workflow_with_job_params(workflow_template, job)
    
    print("-" * 40)
    
    # Verify the results
    print("\nVerification:")
    
    errors = []
    
    # Check PrimitiveStringMultiline got the prompt
    for node_id, node in updated_workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "PrimitiveStringMultiline":
            actual_prompt = node.get("inputs", {}).get("value", "")
            if actual_prompt == test_prompt:
                print(f"✓ PrimitiveStringMultiline ({node_id}): prompt set correctly")
            else:
                errors.append(f"PrimitiveStringMultiline prompt mismatch: got '{actual_prompt[:30]}...'")
                print(f"✗ PrimitiveStringMultiline ({node_id}): WRONG - got '{actual_prompt[:30]}...'")
    
    # Check KSampler got the seed
    for node_id, node in updated_workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            actual_seed = node.get("inputs", {}).get("seed")
            if actual_seed == test_seed:
                print(f"✓ KSampler ({node_id}): seed set correctly to {actual_seed}")
            else:
                errors.append(f"KSampler seed mismatch: expected {test_seed}, got {actual_seed}")
                print(f"✗ KSampler ({node_id}): WRONG - expected {test_seed}, got {actual_seed}")
    
    # Check CLIPTextEncode didn't get overwritten (it should get text from connection)
    for node_id, node in updated_workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
            text_input = node.get("inputs", {}).get("text")
            if isinstance(text_input, list):
                print(f"✓ CLIPTextEncode ({node_id}): text is connection reference (not overwritten)")
            else:
                # It might be okay if it was a direct text input workflow
                print(f"  CLIPTextEncode ({node_id}): text is direct value: '{str(text_input)[:30]}...'")
    
    # Check SaveImage got job ID prefix
    for node_id, node in updated_workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "SaveImage":
            prefix = node.get("inputs", {}).get("filename_prefix", "")
            if "test-job-123" in prefix:
                print(f"✓ SaveImage ({node_id}): filename_prefix set to '{prefix}'")
            else:
                print(f"  SaveImage ({node_id}): filename_prefix is '{prefix}'")
    
    print()
    if errors:
        print(f"✗ FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("✓ All checks passed!")
        return True

def test_with_comfy_api():
    """Actually submit the updated workflow to ComfyUI."""
    import requests
    import time
    
    print("\n" + "=" * 60)
    print("Full Integration Test (via ComfyUI API)")
    print("=" * 60)
    
    # Load workflow
    with open("workflows/image_z_image_turbo_api.json", "r") as f:
        workflow_template = json.load(f)
    
    # Create bridge
    bridge = ComfyUIBridge(
        worker_name="test_worker",
        api_key="test_key",
        workflow_dir="workflows",
        workflow_file="image_z_image_turbo_api.json"
    )
    bridge.workflow_template = workflow_template
    
    # Create job
    job_data = {
        "id": "integration-test-456",
        "model": "z_image_turbo",
        "kudos": 10,
        "payload": {
            "prompt": "Cyberpunk city at night, neon lights, rain reflections, cinematic",
            "negative_prompt": "",
            "seed": 98765,
            "width": 1024,
            "height": 1024,
        }
    }
    job = DummyJobPopResponse(**job_data)
    
    # Update workflow
    print("\nUpdating workflow with job parameters...")
    updated_workflow = bridge._update_workflow_with_job_params(workflow_template, job)
    
    # Submit to ComfyUI
    print(f"Submitting to ComfyUI...")
    payload = {"prompt": updated_workflow}
    response = requests.post("http://127.0.0.1:8188/prompt", json=payload)
    
    if response.status_code != 200:
        print(f"✗ Error: {response.status_code} - {response.text}")
        return False
    
    prompt_id = response.json().get("prompt_id")
    print(f"✓ Queued with prompt_id: {prompt_id}")
    
    # Wait for completion
    print("Waiting for generation...")
    for i in range(60):
        resp = requests.get(f"http://127.0.0.1:8188/history/{prompt_id}")
        if resp.status_code == 200:
            history = resp.json()
            if prompt_id in history and history[prompt_id].get("outputs"):
                print(f"✓ Generation completed!")
                # Find image
                for node_id, output in history[prompt_id]["outputs"].items():
                    if "images" in output:
                        for img in output["images"]:
                            print(f"✓ Generated: {img['filename']}")
                return True
        time.sleep(1)
        print(f"  {i+1}s...", end="\r")
    
    print("✗ Timeout")
    return False

if __name__ == "__main__":
    success = test_bridge_logic()
    
    if success:
        # Also run integration test
        try:
            test_with_comfy_api()
        except Exception as e:
            print(f"\nIntegration test skipped: {e}")
    
    print("\n" + "=" * 60)
