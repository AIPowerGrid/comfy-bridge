import { NextResponse } from 'next/server';
import { startDownload, updateProgress, completeDownload, updateDownloadMessage, failDownload, FileDownloadState, updateFileProgress, setFileStatus, setProcessId, getDownloadState, getAllDownloads } from '@/lib/downloadState';
import { downloadsApiUrl } from '@/lib/serverEnv';
import * as fs from 'fs/promises';
import * as path from 'path';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const pathname = url.pathname;

  // Handle /api/models/download/status
  if (pathname.endsWith('/status')) {
    try {
      const allDownloads = getAllDownloads();
      return NextResponse.json({ models: allDownloads });
    } catch (error) {
      console.error('Error getting download status:', error);
      return NextResponse.json({ error: 'Failed to get download status' }, { status: 500 });
    }
  }

  // Handle /api/models/download/stream
  if (pathname.endsWith('/stream')) {
    // Return a simple SSE stream that can be used for polling
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();

        // Send initial status
        const allDownloads = getAllDownloads();
        const initialData = JSON.stringify({
          type: 'status',
          models: allDownloads,
          timestamp: new Date().toISOString()
        });
        controller.enqueue(encoder.encode(`data: ${initialData}\n\n`));

        // Keep the connection alive with periodic updates
        const interval = setInterval(() => {
          try {
            const allDownloads = getAllDownloads();
            const data = JSON.stringify({
              type: 'status',
              models: allDownloads,
              timestamp: new Date().toISOString()
            });
            controller.enqueue(encoder.encode(`data: ${data}\n\n`));
          } catch (error) {
            console.error('Error in stream:', error);
            controller.close();
            clearInterval(interval);
          }
        }, 2000); // Update every 2 seconds

        // Clean up on close
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
        'X-Accel-Buffering': 'no',
      },
    });
  }

  return NextResponse.json({ error: 'Endpoint not found' }, { status: 404 });
}

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
    
    // Load model configs to get file list
    const defaultConfigPath = path.join(bridgePath, 'model_configs.json');
    const modelConfigPath = process.env.MODEL_CONFIGS_PATH || defaultConfigPath;
    let files: FileDownloadState[] = [];
    
    try {
      const configData = await fs.readFile(modelConfigPath, 'utf-8');
      const modelConfigs = JSON.parse(configData);
      const modelInfo = modelConfigs[models[0]];
      
      if (modelInfo && modelInfo.files && Array.isArray(modelInfo.files)) {
        // Create FileDownloadState objects for each file
        files = modelInfo.files.map((file: any) => ({
          file_name: file.path || 'unknown',
          file_type: file.file_type || 'checkpoints',
          file_size_mb: 0, // Will be updated during download
          progress: 0,
          speed: '',
          eta: '',
          status: 'queued' as const,
          downloaded_mb: 0
        }));
        console.log(`Initialized ${files.length} files for ${models[0]}`);
      }
    } catch (error) {
      console.error('Error loading model configs:', error);
    }
    
    // Start download state tracking
    startDownload(models[0]);
    
        // Call the comfy-bridge API to download models
        const stream = new ReadableStream({
          start(controller) {
            const encoder = new TextEncoder();
            let isClosed = false;
            let sawComplete = false;
            let started = false;
            
            // Helper to safely enqueue data
            const safeEnqueue = (data: Uint8Array) => {
              try {
                if (!isClosed) {
                  controller.enqueue(data);
                }
              } catch (e) {
                console.error('Error enqueuing data (stream may be closed):', e);
                isClosed = true;
              }
            };
            
            // Helper to safely close controller
            const safeClose = () => {
              try {
                if (!isClosed) {
                  controller.close();
                  isClosed = true;
                }
              } catch (e) {
                console.error('Error closing stream (may already be closed):', e);
                isClosed = true;
              }
            };
            
            // Make request to downloads API (separate service)
            const downloadsUrl = downloadsApiUrl('/downloads');
            console.log(`Download route: POST to ${downloadsUrl}`);
            // Immediately emit a local 'start' event so the UI shows activity,
            // even if the backend exits quickly (e.g., already installed).
            try {
              const startEvt = {
                type: 'start',
                model: models[0],
                message: `Starting download for ${models[0]}...`
              };
              safeEnqueue(encoder.encode(`data: ${JSON.stringify(startEvt)}\n\n`));
              started = true;
            } catch (e) {
              console.error('Failed to enqueue local start event', e);
            }
            fetch(downloadsUrl, {
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
              let currentFileName = '';
              
              function pump(): Promise<void> {
                return reader!.read().then(({ done, value }) => {
                  if (done) {
                    // If backend ended without sending an explicit complete, emit one here
                    if (!sawComplete) {
                      const finalEvt = {
                        type: 'complete',
                        success: true,
                        model: models[0],
                        message: started ? 'Download finished' : 'Nothing to download'
                      };
                      safeEnqueue(encoder.encode(`data: ${JSON.stringify(finalEvt)}\n\n`));
                    }
                    safeClose();
                    return;
                  }
                  
                  if (isClosed) {
                    // Stream was closed, stop reading
                    return;
                  }
                  
                  buffer += decoder.decode(value, { stream: true });
                  const lines = buffer.split('\n');
                  buffer = lines.pop() || '';
                  
                  for (const line of lines) {
                    if (line.startsWith('data: ')) {
                      try {
                        const data = JSON.parse(line.slice(6));
                        const currentModel = data.model || models[0];
                        
                        // Parse raw message for file-specific progress
                        const message = data.message || '';
                        
                        // Detect which file is being downloaded: [DOWNLOAD] [1/6] filename.safetensors -> checkpoints/
                        const downloadMatch = message.match(/\[DOWNLOAD\].*?(\S+\.safetensors|\S+\.ckpt|\S+\.pth)/i);
                        if (downloadMatch) {
                          currentFileName = downloadMatch[1];
                          setFileStatus(currentModel, currentFileName, 'downloading');
                        }
                        
                        // Parse progress: [PROGRESS] 38.9% (455.53/1170.14 MB) @ 53.93 MB/s ETA: 13s
                        const progressMatch = message.match(/\[PROGRESS\]\s+([\d.]+)%\s+\(([\d.]+)\/([\d.]+)\s+MB\)\s+@\s+([\d.]+)\s+MB\/s\s+ETA:\s+(.+)/);
                        if (progressMatch && currentFileName) {
                          const progress = parseFloat(progressMatch[1]);
                          const downloaded = parseFloat(progressMatch[2]);
                          const totalMB = parseFloat(progressMatch[3]);
                          const speedMB = parseFloat(progressMatch[4]);
                          const eta = progressMatch[5];
                          
                          updateFileProgress(
                            currentModel,
                            currentFileName,
                            progress,
                            downloaded,
                            speedMB,
                            eta,
                            totalMB
                          );
                        }
                        
                        // Detect file completion: [OK] Downloaded filename.safetensors
                        const completeMatch = message.match(/\[OK\].*?Downloaded\s+(\S+\.safetensors|\S+\.ckpt|\S+\.pth)/i);
                        if (completeMatch) {
                          const fileName = completeMatch[1];
                          setFileStatus(currentModel, fileName, 'completed');
                        }
                        
                        // Update progress based on message type
                        if (data.type === 'process_info' && data.pid) {
                          // Store the process ID for cancellation
                          setProcessId(currentModel, data.pid);
                          console.log(`Download process for ${currentModel} started with PID: ${data.pid}`);
                        } else if (data.type === 'progress' && data.progress !== undefined) {
                          updateProgress(data.progress, data.speed || '', data.eta || '', currentModel, data.message);
                        } else if (data.type === 'complete') {
                          sawComplete = true;
                          if (data.success) {
                            completeDownload(currentModel);
                          } else {
                            failDownload(
                              currentModel,
                              data.message || 'Download failed'
                            );
                          }
                        } else if (data.type === 'start') {
                          updateDownloadMessage(currentModel, data.message || 'Starting download...');
                        } else if (data.type === 'success' || data.type === 'info') {
                          updateDownloadMessage(currentModel, data.message);
                        } else if (data.type === 'error') {
                          failDownload(currentModel, data.message || 'Download failed');
                        }
                        
                        const latestState = getDownloadState(currentModel);
                        if (latestState) {
                          safeEnqueue(encoder.encode(`data: ${JSON.stringify({
                            type: 'status',
                            model: currentModel,
                            state: latestState
                          })}\n\n`));
                        } else {
                          safeEnqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
                        }
                      } catch (e) {
                        console.error('Error parsing SSE data:', e);
                      }
                    }
                  }
                  
                  return pump();
                }).catch(error => {
                  console.error('Error reading stream:', error);
                  // Ensure client unblocks
                  try {
                    const errEvt = {
                      type: 'error',
                      model: models[0],
                      message: `Download stream error: ${error instanceof Error ? error.message : String(error)}`
                    };
                    safeEnqueue(encoder.encode(`data: ${JSON.stringify(errEvt)}\n\n`));
                  } catch {}
                  safeClose();
                });
              }
              
              return pump();
            }).catch(error => {
              console.error('Download API error (connecting to 8002):', error);
              const errorData = JSON.stringify({
                type: 'error',
                message: `Download API error: ${error.message}`,
                timestamp: new Date().toISOString()
              });
              safeEnqueue(encoder.encode(`data: ${errorData}\n\n`));
              safeClose();
            });
          }
        });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no', // Disable nginx buffering
      },
    });
  } catch (error: any) {
    console.error('Download error:', error);
    
    return NextResponse.json({
      success: false,
      error: error.message || 'Unknown error',
    }, { status: 500 });
  }
}

