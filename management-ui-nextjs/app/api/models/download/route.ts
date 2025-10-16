import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { startDownload, updateProgress, completeDownload } from '@/lib/downloadState';

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
    
    // Start download state tracking
    startDownload(models[0]); // Track first model
    
        // Call the comfy-bridge API to download models
        const stream = new ReadableStream({
          start(controller) {
            const encoder = new TextEncoder();
            
            // Make request to comfy-bridge API
            fetch('http://comfy-bridge:8001/api/download-models', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ models })
            }).then(response => {
              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
              }
              
              const reader = response.body?.getReader();
              if (!reader) {
                throw new Error('No response body');
              }
              
              const decoder = new TextDecoder();
              let buffer = '';
              
              function pump(): Promise<void> {
                return reader!.read().then(({ done, value }) => {
                  if (done) {
                    controller.close();
                    return;
                  }
                  
                  buffer += decoder.decode(value, { stream: true });
                  const lines = buffer.split('\n');
                  buffer = lines.pop() || '';
                  
                  for (const line of lines) {
                    if (line.startsWith('data: ')) {
                      try {
                        const data = JSON.parse(line.slice(6));
                        
                        // Update progress if it's a progress update
                        if (data.type === 'progress' && data.progress !== undefined) {
                          updateProgress(data.progress, data.speed, data.eta);
                        } else if (data.type === 'complete') {
                          completeDownload();
                        } else if (data.type === 'start') {
                          startDownload(data.model || models[0]);
                        }
                        
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
                      } catch (e) {
                        console.error('Error parsing SSE data:', e);
                      }
                    }
                  }
                  
                  return pump();
                });
              }
              
              return pump();
            }).catch(error => {
              console.error('Download API error:', error);
              const errorData = JSON.stringify({
                type: 'error',
                message: `Download API error: ${error.message}`,
                timestamp: new Date().toISOString()
              });
              controller.enqueue(encoder.encode(`data: ${errorData}\n\n`));
              controller.close();
            });
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

