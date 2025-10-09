import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
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
        
        // Run the download script directly in this container (it has access to mounted files)
        const { stdout, stderr } = await execAsync(
          `python3 /app/comfy-bridge/download_models_from_catalog.py --models "${modelsList}" --models-path /app/ComfyUI/models`,
          {
            cwd: bridgePath,
            timeout: 3600000, // 1 hour
            env: env
          }
        );
    
    console.log('Download stdout:', stdout);
    if (stderr) console.log('Download stderr:', stderr);
    
    return NextResponse.json({
      success: true,
      message: `Downloaded ${models.length} models successfully`,
      models: models,
      output: stdout,
      error: stderr || null,
    });
  } catch (error: any) {
    console.error('Download error:', error);
    
    if (error.code === 'TIMEOUT') {
      return NextResponse.json({
        success: false,
        error: 'Download timed out after 1 hour',
      }, { status: 408 });
    }
    
    return NextResponse.json({
      success: false,
      error: error.message || 'Unknown error',
      output: error.stdout || '',
      stderr: error.stderr || '',
    }, { status: 500 });
  }
}

