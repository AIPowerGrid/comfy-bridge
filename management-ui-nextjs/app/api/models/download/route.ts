import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const isWindows = process.platform === 'win32';

// Get the comfy-bridge downloads API URL
function getDownloadsApiUrl() {
  if (isWindows) {
    return 'http://localhost:8002';
  }
  // In Docker, use the container name
  return 'http://comfy-bridge:8002';
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
    
    // Create SSE stream that proxies from comfy-bridge downloads API
    const encoder = new TextEncoder();
    
    const stream = new ReadableStream({
      async start(controller) {
        const sendEvent = (data: any) => {
          try {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
          } catch (e) {
            // Stream may be closed
          }
        };
        
        sendEvent({ type: 'start', model: modelName, message: `Starting download for ${modelName}...` });
        
        try {
          const downloadsApiUrl = getDownloadsApiUrl();
          console.log(`Calling downloads API at ${downloadsApiUrl}/downloads`);
          
          // Call the comfy-bridge downloads API
          const response = await fetch(`${downloadsApiUrl}/downloads`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ models }),
          });
          
          if (!response.ok) {
            throw new Error(`Downloads API returned ${response.status}`);
          }
          
          // Check if response is SSE
          const contentType = response.headers.get('content-type');
          if (contentType?.includes('text/event-stream')) {
            // Stream the SSE response
            const reader = response.body?.getReader();
            if (reader) {
              const decoder = new TextDecoder();
              let buffer = '';
              
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                  if (line.startsWith('data: ')) {
                    try {
                      const data = JSON.parse(line.slice(6));
                      sendEvent(data);
                    } catch (e) {
                      // Invalid JSON, skip
                    }
                  }
                }
              }
            }
          } else {
            // JSON response
            const result = await response.json();
            if (result.success) {
              sendEvent({ type: 'complete', model: modelName, message: result.message || 'Download complete' });
            } else {
              sendEvent({ type: 'error', model: modelName, message: result.message || 'Download failed' });
            }
          }
          
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
