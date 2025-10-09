import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    const modelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';
    const repoPath = process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH || '/app/grid-image-model-reference';
    const bridgePath = process.env.COMFY_BRIDGE_PATH || '/app/comfy-bridge';
    
    console.log('Uninstalling model:', model_id);
    
    // Load model info from catalog
    const catalogPath = path.join(repoPath, 'stable_diffusion.json');
    const catalogContent = await fs.readFile(catalogPath, 'utf-8');
    const catalog = JSON.parse(catalogContent);
    
    const modelInfo = catalog[model_id];
    if (!modelInfo) {
      return NextResponse.json({ error: 'Model not found in catalog' }, { status: 404 });
    }
    
    const files = modelInfo.config?.files || [];
    const deletedFiles: string[] = [];
    
    // Delete all files associated with this model
    for (const file of files) {
      const fileName = path.basename(file.path);
      const fileType = file.file_type || 'checkpoints'; // Default to checkpoints
      
      // Map file types to directories
      const typeToDir: { [key: string]: string } = {
        'checkpoint': 'checkpoints',
        'vae': 'vae',
        'clip': 'clip',
        'lora': 'loras',
        'unet': 'unet',
        'diffusion': 'diffusion_models',
        'text_encoder': 'text_encoders',
      };
      
      const targetDir = typeToDir[fileType] || 'checkpoints';
      const filePath = path.join(modelsPath, targetDir, fileName);
      
      try {
        await fs.access(filePath);
        await fs.unlink(filePath);
        deletedFiles.push(filePath);
        console.log(`Deleted: ${filePath}`);
      } catch (err) {
        console.log(`File not found: ${filePath}`);
      }
    }
    
    if (deletedFiles.length === 0) {
      return NextResponse.json({ 
        error: 'Model files not found',
        success: false,
      }, { status: 404 });
    }
    
    return NextResponse.json({ 
      success: true,
      deleted_files: deletedFiles,
      model_id,
      message: `Successfully uninstalled ${model_id}`,
    });
  } catch (error: any) {
    console.error('Uninstall error:', error);
    return NextResponse.json({ 
      error: error.message,
      success: false,
    }, { status: 500 });
  }
}
