import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

interface RemovalItem {
  name: string;
  type: 'model' | 'dependency' | 'file';
  path: string;
  size?: number;
}

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    const modelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';
    const catalogPath = process.env.MODEL_CONFIGS_PATH || '/app/comfy-bridge/model_configs.json';
    const stableDiffusionPath = process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH 
      ? `${process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH}/stable_diffusion.json`
      : '/app/grid-image-model-reference/stable_diffusion.json';
    const bridgePath = process.env.COMFY_BRIDGE_PATH || '/app/comfy-bridge';
    
    console.log('Uninstalling model:', model_id);
    
    // Load comprehensive catalog from stable_diffusion.json
    let modelInfo: any = null;
    try {
      const sdContent = await fs.readFile(stableDiffusionPath, 'utf-8');
      const sdCatalog = JSON.parse(sdContent);
      modelInfo = sdCatalog[model_id];
    } catch (error) {
      console.warn('Could not load stable_diffusion.json:', error);
    }
    
    // Fallback to model_configs.json
    if (!modelInfo) {
      const catalogContent = await fs.readFile(catalogPath, 'utf-8');
      const catalog = JSON.parse(catalogContent);
      modelInfo = catalog[model_id];
    }
    
    if (!modelInfo) {
      return NextResponse.json({ error: 'Model not found in catalog' }, { status: 404 });
    }
    
    const removedItems: RemovalItem[] = [];
    
    // Get all files to delete from config.download[], files[], or simple format
    let filesToDelete: Array<{name: string; folder: string}> = [];
    
    // Check for files[] array (model_configs.json format)
    if (modelInfo.files && Array.isArray(modelInfo.files)) {
      console.log(`Found ${modelInfo.files.length} files in model_configs.json format`);
      for (const file of modelInfo.files) {
        const fileName = file.path || file.file_name;
        const folder = file.file_type || 'checkpoints';
        if (fileName) {
          filesToDelete.push({ name: fileName, folder });
        }
      }
    }
    // Check for config.download[] (stable_diffusion.json format)
    else if (modelInfo.config && modelInfo.config.download && Array.isArray(modelInfo.config.download)) {
      console.log(`Found ${modelInfo.config.download.length} files in stable_diffusion.json format`);
      for (const download of modelInfo.config.download) {
        const fileName = download.file_name;
        const fileUrl = download.file_url;
        
        // Determine folder from URL
        let folder = 'checkpoints';
        if (fileUrl.includes('/vae/')) folder = 'vae';
        else if (fileUrl.includes('/loras/') || fileUrl.includes('/lora/')) folder = 'loras';
        else if (fileUrl.includes('/text_encoders/') || fileUrl.includes('/clip/')) folder = 'text_encoders';
        else if (fileUrl.includes('/diffusion_models/') || fileUrl.includes('/unet/')) folder = 'diffusion_models';
        
        filesToDelete.push({ name: fileName, folder });
      }
    }
    // Fallback to simple format
    else if (modelInfo.filename) {
      console.log('Found filename in simple format');
      const fileType = modelInfo.type || 'checkpoints';
      filesToDelete.push({ name: modelInfo.filename, folder: fileType });
    }
    
    console.log(`Total files to delete: ${filesToDelete.length}`);
    
    // Delete all files
    for (const file of filesToDelete) {
      const filePath = path.join(modelsPath, file.folder, file.name);
      
      try {
        const stats = await fs.stat(filePath);
        await fs.unlink(filePath);
        
        removedItems.push({
          name: file.name,
          type: 'file',
          path: `${file.folder}/${file.name}`,
          size: stats.size
        });
        
        console.log(`Deleted: ${filePath}`);
      } catch (err: any) {
        if (err.code !== 'ENOENT') {
          console.error(`Failed to delete file: ${filePath}`, err);
        }
      }
    }
    
    // Get dependencies from model info
    const dependencies = modelInfo.dependencies || [];
    
    // Delete dependency files if they exist
    for (const dep of dependencies) {
      if (typeof dep === 'string') {
        // Dependency is just a model ID - would need to look it up
        // For now, skip
        console.log(`Skipping dependency (ID only): ${dep}`);
      } else if (dep.filename) {
        const depType = dep.type || 'checkpoints';
        const depPath = path.join(modelsPath, depType, dep.filename);
        
        try {
          const stats = await fs.stat(depPath);
          await fs.unlink(depPath);
          
          removedItems.push({
            name: dep.filename,
            type: 'dependency',
            path: `${depType}/${dep.filename}`,
            size: stats.size
          });
          
          console.log(`Deleted dependency: ${depPath}`);
        } catch (err: any) {
          if (err.code !== 'ENOENT') {
            console.error(`Failed to delete dependency: ${depPath}`, err);
          }
        }
      }
    }
    
    // Always check and remove from WORKFLOW_FILE, even if no files were deleted
    let removedFromWorkflow = false;
    try {
      const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
      let envContent = await fs.readFile(envFilePath, 'utf-8');
      
      const match = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
      if (match && match[1]) {
        const currentModels = match[1].split(',')
          .map(s => {
            const trimmed = s.trim();
            return trimmed.endsWith('.json') ? trimmed.slice(0, -5) : trimmed;
          })
          .filter(Boolean);
        
        const modelIdWithoutJson = model_id.endsWith('.json') ? model_id.slice(0, -5) : model_id;
        const filtered = currentModels.filter(m => m !== modelIdWithoutJson);
        
        if (filtered.length !== currentModels.length) {
          envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${filtered.join(',')}`);
          await fs.writeFile(envFilePath, envContent, 'utf-8');
          console.log(`Removed ${model_id} from WORKFLOW_FILE`);
          removedFromWorkflow = true;
        }
      }
    } catch (error) {
      console.error('Failed to update WORKFLOW_FILE:', error);
    }
    
    // If no files were deleted but model was in WORKFLOW_FILE, still consider it a success
    if (removedItems.length === 0 && !removedFromWorkflow) {
      return NextResponse.json({ 
        error: 'Model not found. No files to delete and not in WORKFLOW_FILE.',
        success: false,
      }, { status: 404 });
    }
    
    // Return summary of removed items (UI will show dialog if files were removed, then trigger restart)
    const message = removedItems.length > 0 
      ? `Successfully uninstalled ${model_id}. ${removedItems.length} item(s) removed.`
      : `Removed ${model_id} from configuration.`;
    
    return NextResponse.json({ 
      success: true,
      removed_items: removedItems,
      model_id,
      message,
      requires_restart: removedFromWorkflow || removedItems.length > 0,
    });
  } catch (error: any) {
    console.error('Uninstall error:', error);
    return NextResponse.json({ 
      error: error.message,
      success: false,
    }, { status: 500 });
  }
}
