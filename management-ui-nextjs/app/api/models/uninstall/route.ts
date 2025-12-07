import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';

export const dynamic = 'force-dynamic';

const isWindows = process.platform === 'win32';

function getEnvPath() {
  if (isWindows) {
    return process.env.ENV_FILE_PATH || 'c:\\dev\\comfy-bridge\\.env';
  }
  return process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
}

function getModelsPath() {
  if (isWindows) {
    return process.env.MODELS_PATH || 'c:\\dev\\comfy-bridge\\persistent_volumes\\models';
  }
  return process.env.MODELS_PATH || '/app/ComfyUI/models';
}

async function findModelFiles(modelName: string): Promise<{ path: string; name: string; size: number; type: string }[]> {
  const modelsPath = getModelsPath();
  const foundFiles: { path: string; name: string; size: number; type: string }[] = [];
  
  const dirsToScan = [
    { dir: 'checkpoints', type: 'checkpoint' },
    { dir: 'diffusion_models', type: 'diffusion_model' },
    { dir: 'unet', type: 'unet' },
    { dir: 'vae', type: 'vae' },
    { dir: 'clip', type: 'text_encoder' },
    { dir: 'text_encoders', type: 'text_encoder' },
    { dir: 'loras', type: 'lora' },
  ];
  
  const normalizedName = modelName.toLowerCase().replace(/[^a-z0-9]/g, '');
  
  for (const { dir, type } of dirsToScan) {
    try {
      const dirPath = path.join(modelsPath, dir);
      const files = await fs.readdir(dirPath);
      
      for (const file of files) {
        if (!file.endsWith('.safetensors') && !file.endsWith('.ckpt') && !file.endsWith('.pt')) {
          continue;
        }
        
        const normalizedFile = file.toLowerCase().replace(/[^a-z0-9]/g, '');
        
        // Check if file matches model name
        if (normalizedFile.includes(normalizedName) || normalizedName.includes(normalizedFile.replace('safetensors', '').replace('ckpt', ''))) {
          const filePath = path.join(dirPath, file);
          const stats = await fs.stat(filePath);
          foundFiles.push({
            path: filePath,
            name: file,
            size: stats.size,
            type,
          });
        }
      }
    } catch (err) {
      // Directory doesn't exist
    }
  }
  
  return foundFiles;
}

async function removeFromWorkflowFile(modelId: string): Promise<boolean> {
  const envPath = getEnvPath();
  
  try {
    let envContent = await fs.readFile(envPath, 'utf-8');
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    
    if (!workflowMatch || !workflowMatch[1]) {
      return false;
    }
    
    let currentWorkflows = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
    const originalLength = currentWorkflows.length;
    
    const modelVariations = [
      modelId,
      `${modelId}.json`,
      modelId.toLowerCase(),
      `${modelId.toLowerCase()}.json`,
    ];
    
    currentWorkflows = currentWorkflows.filter(w => {
      const wLower = w.toLowerCase();
      const wNoJson = w.replace(/\.json$/, '').toLowerCase();
      return !modelVariations.some(v => v.toLowerCase() === wLower || v.toLowerCase() === wNoJson);
    });
    
    if (currentWorkflows.length !== originalLength) {
      const newWorkflowValue = currentWorkflows.join(',');
      envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newWorkflowValue}`);
      await fs.writeFile(envPath, envContent, 'utf-8');
      return true;
    }
    
    return false;
  } catch (err) {
    console.error('Error updating workflow file:', err);
    return false;
  }
}

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    
    if (!model_id) {
      return NextResponse.json({
        success: false,
        error: 'Model ID is required'
      }, { status: 400 });
    }
    
    console.log(`Uninstalling model: ${model_id}`);
    
    // Find model files
    const modelFiles = await findModelFiles(model_id);
    const removedItems: { name: string; type: string; size: number }[] = [];
    
    // Delete files
    for (const file of modelFiles) {
      try {
        await fs.unlink(file.path);
        removedItems.push({
          name: file.name,
          type: file.type,
          size: file.size,
        });
        console.log(`Deleted: ${file.path}`);
      } catch (err) {
        console.error(`Failed to delete ${file.path}:`, err);
      }
    }
    
    // Remove from WORKFLOW_FILE
    const workflowUpdated = await removeFromWorkflowFile(model_id);
    
    // Determine if restart is needed
    const requiresRestart = workflowUpdated || removedItems.length > 0;
    
    if (removedItems.length === 0 && !workflowUpdated) {
      return NextResponse.json({
        success: true,
        requires_restart: false,
        message: `No files found for ${model_id}`,
        removed_items: []
      });
    }
    
    // Trigger container restart if needed
    if (requiresRestart) {
      try {
        const { exec } = await import('child_process');
        const { promisify } = await import('util');
        const execAsync = promisify(exec);
        
        if (isWindows) {
          await execAsync('docker-compose restart comfy-bridge', { 
            cwd: 'c:\\dev\\comfy-bridge' 
          });
        } else {
          await execAsync('docker-compose -f /app/comfy-bridge/docker-compose.yml restart comfy-bridge');
        }
      } catch (restartError) {
        console.error('Failed to restart container:', restartError);
      }
    }
    
    return NextResponse.json({
      success: true,
      requires_restart: requiresRestart,
      message: `Uninstalled ${model_id}`,
      removed_items: removedItems
    });
    
  } catch (error: any) {
    console.error('Error uninstalling model:', error);
    return NextResponse.json({
      success: false,
      error: error.message || 'Failed to uninstall model'
    }, { status: 500 });
  }
}
