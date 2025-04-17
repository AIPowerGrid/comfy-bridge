# ComfyUI Bridge for AI Power Grid - Developer Documentation

This document provides technical details about the implementation of the ComfyUI bridge for AI Power Grid.

## Architecture Overview

The bridge consists of the following components:

1. **`bridge.py`** - The main bridge module that handles:
   - Connection to the AI Power Grid API
   - Job queue management
   - Converting AI Power Grid jobs to ComfyUI workflows
   - Submitting workflows to ComfyUI
   - Returning results to AI Power Grid

2. **`setup.py`** - Setup script that:
   - Installs dependencies
   - Sets up ComfyUI (if not already installed)
   - Creates configuration files
   - Generates launcher scripts

3. **`start_bridge.py`** - Launcher script that:
   - Loads environment variables
   - Configures the bridge
   - Starts the bridge

## Integration with AI Power Grid

The bridge communicates with the AI Power Grid API using the following endpoints:

- `/v2/workers` - Register worker
- `/v2/workers` - Unregister worker
- `/v2/generate/pop` - Get jobs
- `/v2/generate/submit` - Submit completed jobs

The API communication follows the standard AI Power Grid protocol, with the bridge identifying itself using the `bridge_agent` field.

## Integration with ComfyUI

The bridge communicates with ComfyUI using its HTTP API:

- `POST /prompt` - Submit workflows
- `GET /history/{prompt_id}` - Check job status
- `GET /view?filename={filename}` - Get generated images

ComfyUI exposes its API on port 8000 by default, and the bridge connects to it using the httpx library for async HTTP requests.

## Job Processing Workflow

1. **Job Retrieval**:
   - Bridge registers as a worker with AI Power Grid
   - Periodically polls for new jobs
   - When a job is available, it's added to the processing queue

2. **Job Conversion**:
   - AI Power Grid job parameters are mapped to a ComfyUI workflow
   - This includes model selection, prompt, negative prompt, size, etc.
   - The workflow is formatted as a JSON object compatible with ComfyUI

3. **Workflow Execution**:
   - The workflow is submitted to ComfyUI
   - Bridge polls ComfyUI for job completion
   - Once complete, the generated image is retrieved

4. **Result Submission**:
   - The image is converted to base64
   - Submitted back to AI Power Grid
   - Job is marked as completed

## Challenges and Considerations

### Model Mapping

AI Power Grid uses standardized model names, while ComfyUI uses the actual filenames of the models. The bridge includes a mapping function to convert between these naming conventions.

### Error Handling

The bridge includes robust error handling to manage:
- Connection failures to AI Power Grid
- Connection failures to ComfyUI
- Failed generations
- Timeout situations

### Concurrency

The bridge supports running multiple jobs concurrently through:
- Async/await pattern
- Task management with asyncio
- Configurable number of threads

## Further Development

Areas for potential improvement:

1. **Enhanced Workflow Conversion**:
   - Support more complex AI Power Grid parameters
   - Better mapping of samplers and schedulers
   - Support for advanced features like img2img, inpainting, etc.

2. **Model Management**:
   - Dynamic model discovery and reporting
   - Automatic model downloading

3. **Performance Optimization**:
   - Better memory management
   - GPU utilization tracking
   - Smart scheduling based on resource availability

4. **UI Integration**:
   - Web UI for monitoring and configuration
   - Integration with ComfyUI's own UI

5. **Extended Compatibility**:
   - Support for ComfyUI extensions and custom nodes
   - Support for ControlNet, LoRA, etc. 