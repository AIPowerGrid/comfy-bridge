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
    const catalogPath = process.env.MODEL_CONFIGS_PATH || '/app/comfy-bridge/model_configs.json';
    const bridgePath = process.env.COMFY_BRIDGE_PATH || '/app/comfy-bridge';
    
    console.log('Uninstalling model:', model_id);
    
    // First, stop hosting the model if it's currently being hosted
    try {
      const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
      let envContent = await fs.readFile(envFilePath, 'utf-8');
      
      // Check if model is currently being hosted
      const match = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
      let currentModels: string[] = [];
      
      if (match && match[1]) {
        currentModels = match[1].split(',').map(s => s.trim()).filter(Boolean);
      }
      
      // If model is being hosted, stop hosting it first
      if (currentModels.includes(model_id)) {
        console.log(`Stopping hosting for model: ${model_id}`);
        currentModels = currentModels.filter(m => m !== model_id);
        const newModelsValue = currentModels.join(',');
        
        // Update WORKFLOW_FILE
        if (match) {
          envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newModelsValue}`);
        }
        
        await fs.writeFile(envFilePath, envContent, 'utf-8');
        console.log(`Model ${model_id} is no longer being hosted`);
      }
    } catch (hostingError) {
      console.warn('Failed to stop hosting model:', hostingError);
      // Continue with uninstall even if hosting stop fails
    }
    
    // Load model info from catalog
    const catalogContent = await fs.readFile(catalogPath, 'utf-8');
    const catalog = JSON.parse(catalogContent);
    
    const modelInfo = catalog[model_id];
    if (!modelInfo) {
      return NextResponse.json({ error: 'Model not found in catalog' }, { status: 404 });
    }
    
    const deletedFiles: string[] = [];
    
    // Delete main model file
    const filename = modelInfo.filename;
    const fileType = modelInfo.type || 'checkpoints';
    
    // Map file types to directories
    const typeToDir: { [key: string]: string } = {
      'checkpoints': 'checkpoints',
      'vae': 'vae',
      'clip': 'clip',
      'loras': 'loras',
      'unet': 'unet',
      'diffusion_models': 'diffusion_models',
      'text_encoders': 'text_encoders',
    };
    
    const targetDir = typeToDir[fileType] || 'checkpoints';
    const filePath = path.join(modelsPath, targetDir, filename);
    
    try {
      await fs.access(filePath);
      await fs.unlink(filePath);
      deletedFiles.push(filePath);
      console.log(`Deleted: ${filePath}`);
    } catch (err) {
      console.log(`File not found: ${filePath}`);
    }
    
    // Delete dependency files
    for (const dep of modelInfo.dependencies || []) {
      const depFilename = dep.filename;
      const depType = dep.type || 'checkpoints';
      const depTargetDir = typeToDir[depType] || 'checkpoints';
      const depFilePath = path.join(modelsPath, depTargetDir, depFilename);
      
      try {
        await fs.access(depFilePath);
        await fs.unlink(depFilePath);
        deletedFiles.push(depFilePath);
        console.log(`Deleted dependency: ${depFilePath}`);
      } catch (err) {
        console.log(`Dependency file not found: ${depFilePath}`);
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
