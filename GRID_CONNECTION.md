# Connecting to AI Power Grid Network

This guide will help you connect your local ComfyUI installation to the AI Power Grid distributed network as an image worker.

## Prerequisites

1. **ComfyUI Installation**: Make sure your ComfyUI is running on your computer
2. **AI Power Grid Account**: Register at [AI Power Grid](https://aipowergrid.io/register) to get an API key
3. **Python Environment**: Make sure you've installed the required dependencies

## Steps to Connect

### 1. Get Your API Key

1. Go to [AI Power Grid Registration Page](https://aipowergrid.io/register)
2. Create an account or log in
3. Find your API key in your user profile

### 2. Set Up Environment

There are two ways to provide your API key:

**Option 1: Environment File**
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit the `.env` file and replace `YOUR_API_KEY_HERE` with your actual API key
3. Customize other settings if needed

**Option 2: Command Line Arguments**
When running the bridge, you can provide your API key and other settings directly:
```bash
python start_bridge.py --api-key YOUR_API_KEY_HERE
```

### 3. Run the Bridge

Start the bridge with:
```bash
python start_bridge.py
```

If you have a custom environment file:
```bash
python start_bridge.py --env-file .env.custom
```

Additional options:
```bash
python start_bridge.py --worker-name "My-ComfyUI-Worker" --threads 2 --nsfw
```

### Available Options

- `--api-key`: Your AI Power Grid API key
- `--worker-name`: Name for your worker (default: ComfyUI-Bridge-Worker)
- `--comfy-url`: URL to ComfyUI (default: http://127.0.0.1:8000)
- `--nsfw`: Allow NSFW content
- `--threads`: Number of concurrent jobs to process (default: 1)
- `--env-file`: Environment file to load (default: .env)

## What to Expect

Once connected, your worker will:

1. Register with AI Power Grid
2. Announce available models
3. Begin polling for jobs
4. Process jobs as they become available
5. Submit completed images back to the network

## Earning Kudos

By processing images for the network, you earn "kudos" which can be used to generate images through the network. The more jobs you process, the more kudos you earn.

## Troubleshooting

If you encounter issues:

1. Check that ComfyUI is running and accessible at the URL specified
2. Verify your API key is correct
3. Make sure your models are loaded correctly in ComfyUI
4. Check the log file for detailed logs

## Stopping the Worker

Press Ctrl+C to gracefully stop the worker. This will complete any current jobs and properly unregister from the network. 