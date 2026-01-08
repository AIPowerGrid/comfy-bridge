#!/usr/bin/env python3
"""Check a specific job ID to see why it's not being popped."""
import asyncio
import json
import sys
from comfy_bridge.api_client import APIClient
from comfy_bridge.config import Settings

async def check_job(job_id: str):
    """Check job details and worker compatibility."""
    api = APIClient()
    
    print(f"Checking job: {job_id}")
    print(f"Worker: {Settings.GRID_WORKER_NAME}")
    print(f"API URL: {Settings.GRID_API_URL}")
    print()
    
    try:
        # Get job status
        try:
            status = await api.get_request_status(job_id)
            print("=" * 60)
            print("JOB STATUS:")
            print("=" * 60)
            print(json.dumps(status, indent=2))
            print()
            
            # Try to get more details - check if there's a model field
            job_model = status.get("model")
            if job_model:
                print(f"Job is requesting model: '{job_model}'")
            else:
                print("No model field in status - checking request details...")
        except Exception as e:
            print(f"Could not get job status: {e}")
            status = {}
        
        # Get models status to see what we're advertising
        models_status = await api.get_models_status()
        print("=" * 60)
        print("MODELS STATUS:")
        print("=" * 60)
        
        job_model = status.get("model")
        if job_model:
            print(f"Job model: '{job_model}'")
            print()
            
            # Find this model in the queue
            for model_info in models_status:
                if isinstance(model_info, dict):
                    name = model_info.get("name", "")
                    if name == job_model:
                        queued = model_info.get("queued", 0)
                        jobs = model_info.get("jobs", 0)
                        print(f"Found model '{name}' in queue:")
                        print(f"  Jobs: {jobs}")
                        print(f"  Megapixels: {queued:.0f}")
                        break
        
        print()
        print("Our advertised models:", Settings.GRID_MODELS)
        print()
        
        # Try to pop a job to see what happens
        print("=" * 60)
        print("ATTEMPTING TO POP JOB:")
        print("=" * 60)
        pop_result = await api.pop_job(Settings.GRID_MODELS)
        
        if pop_result.get("id"):
            print(f"✅ Got job: {pop_result.get('id')}")
            print(f"   Model: {pop_result.get('model')}")
        else:
            print("❌ No job assigned")
            skipped = pop_result.get("skipped", {})
            if skipped:
                print(f"Skipped reasons: {json.dumps(skipped, indent=2)}")
            else:
                print("No skipped reasons provided")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.client.aclose()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_job.py <job_id>")
        sys.exit(1)
    
    job_id = sys.argv[1]
    asyncio.run(check_job(job_id))
