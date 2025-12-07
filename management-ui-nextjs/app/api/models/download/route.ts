import { NextResponse } from 'next/server';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

const isWindows = process.platform === 'win32';

function getComfyBridgePath() {
  if (isWindows) {
    return 'c:\\dev\\comfy-bridge';
  }
  return '/app/comfy-bridge';
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const pathname = url.pathname;

  // Handle /api/models/download/status
  if (pathname.endsWith('/status')) {
    return NextResponse.json({ 
      models: [],
      message: 'Download status endpoint'
    });
  }

  // Handle /api/models/download/stream - SSE for progress
  if (pathname.endsWith('/stream')) {
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'connected' })}\n\n`));
        
        // Keep alive
        const interval = setInterval(() => {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'heartbeat' })}\n\n`));
        }, 5000);
        
        request.signal.addEventListener('abort', () => {
          clearInterval(interval);
          controller.close();
        });
      }
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
      },
    });
  }

  return NextResponse.json({ error: 'Endpoint not found' }, { status: 404 });
}

export async function POST(request: Request): Promise<Response> {
  try {
    const { models } = await request.json();
    
    if (!models || models.length === 0) {
      return NextResponse.json({ 
        error: 'No models specified',
        success: false 
      }, { status: 400 });
    }
    
    const modelName = models[0];
    console.log('Starting download for model:', modelName);
    
    // Create SSE stream for progress updates
    const encoder = new TextEncoder();
    
    const stream = new ReadableStream({
      async start(controller) {
        const sendEvent = (data: any) => {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        };
        
        sendEvent({ type: 'start', model: modelName, message: `Starting download for ${modelName}...` });
        
        try {
          const bridgePath = getComfyBridgePath();
          
          // Use the download_models_from_chain.py script
          const downloadScript = isWindows 
            ? `python "${bridgePath}\\download_models_from_chain.py"`
            : `python3 ${bridgePath}/download_models_from_chain.py`;
          
          // Set environment variables for the download
          const env = {
            ...process.env,
            MODELS_TO_DOWNLOAD: modelName,
            MODELVAULT_CONTRACT: process.env.MODELVAULT_CONTRACT || '0xF5caaB067Bae8ea6Be18903056E20e8DacB92182',
            MODELVAULT_RPC: process.env.MODELVAULT_RPC || 'https://sepolia.base.org',
          };
          
          sendEvent({ type: 'progress', model: modelName, message: 'Connecting to blockchain...', progress: 5 });
          
          // Execute the download script
          // For now, we'll use exec with a timeout
          const { stdout, stderr } = await execAsync(downloadScript, {
            cwd: bridgePath,
            env,
            timeout: 3600000, // 1 hour timeout for large models
          });
          
          if (stderr && stderr.includes('Error')) {
            throw new Error(stderr);
          }
          
          sendEvent({ type: 'complete', model: modelName, message: `${modelName} downloaded successfully!` });
          
        } catch (error: any) {
          console.error('Download error:', error);
          sendEvent({ type: 'error', model: modelName, message: error.message || 'Download failed' });
        } finally {
          controller.close();
        }
      }
    });
    
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
      },
    });
    
  } catch (error: any) {
    console.error('Failed to start download:', error);
    return NextResponse.json({
      error: 'Failed to start download',
      message: error.message,
      success: false
    }, { status: 500 });
  }
}
