import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<Response> {
  try {
    const { models } = await request.json();
    const bridgePath = process.env.COMFY_BRIDGE_PATH || '/app/comfy-bridge';
    
    if (!models || models.length === 0) {
      return NextResponse.json({ 
        error: 'No models specified',
        success: false 
      }, { status: 400 });
    }
    
    console.log('Starting download for models:', models);
    
        // Run the download script in the comfy-bridge container which has correct permissions
        const modelsList = models.join(',');
        const env = {
          ...process.env,
          HUGGING_FACE_API_KEY: process.env.HUGGING_FACE_API_KEY || '',
          CIVITAI_API_KEY: process.env.CIVITAI_API_KEY || '',
          GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH: process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH || '/app/grid-image-model-reference'
        };
        
        // Stream download progress using Server-Sent Events
        const encoder = new TextEncoder();
        
        const stream = new ReadableStream({
          start(controller) {
            const child = spawn('python3', [
              '/app/comfy-bridge/download_models_from_catalog.py',
              '--models', modelsList,
              '--models-path', '/app/ComfyUI/models',
              '--config', '/app/comfy-bridge/model_configs.json'
            ], {
              cwd: bridgePath,
              env: env,
              stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

            child.stdout.on('data', (data) => {
              const chunk = data.toString();
              stdout += chunk;
              console.log('Download progress:', chunk.trim());
              
              // Send progress update to client
              const progressData = JSON.stringify({
                type: 'progress',
                message: chunk.trim(),
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${progressData}\n\n`));
            });

            child.stderr.on('data', (data) => {
              const chunk = data.toString();
              stderr += chunk;
              console.log('Download stderr:', chunk.trim());
              
              // Send error update to client
              const errorData = JSON.stringify({
                type: 'error',
                message: chunk.trim(),
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${errorData}\n\n`));
            });

            child.on('close', (code) => {
              console.log('Download completed with code:', code);
              
              const resultData = JSON.stringify({
                type: 'complete',
                success: code === 0,
                message: code === 0 ? `Downloaded ${models.length} models successfully` : `Download failed with exit code ${code}`,
                models: models,
                output: stdout,
                error: stderr || null,
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${resultData}\n\n`));
              controller.close();
            });

            child.on('error', (error) => {
              console.error('Download spawn error:', error);
              const errorData = JSON.stringify({
                type: 'error',
                message: `Download spawn error: ${error.message}`,
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${errorData}\n\n`));
              controller.close();
            });

            // Set timeout
            setTimeout(() => {
              child.kill();
              const timeoutData = JSON.stringify({
                type: 'error',
                message: 'Download timed out after 1 hour',
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${timeoutData}\n\n`));
              controller.close();
            }, 3600000);
          }
        });

        return new Response(stream, {
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        });
  } catch (error: any) {
    console.error('Download error:', error);
    
    if (error.message && error.message.includes('timed out')) {
      return NextResponse.json({
        success: false,
        error: 'Download timed out after 1 hour',
      }, { status: 408 });
    }
    
    return NextResponse.json({
      success: false,
      error: error.message || 'Unknown error',
      output: '',
      stderr: '',
    }, { status: 500 });
  }
}

