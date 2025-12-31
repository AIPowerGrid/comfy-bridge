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

// Model-specific file mappings for complex models with multiple files
// Note: text_encoders (like umt5_xxl_fp8_e4m3fn_scaled.safetensors) are excluded 
// because they are shared between models
const MODEL_FILE_PATTERNS: Record<string, string[]> = {
  'wan2.2-t2v-a14b': [
    // 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', // text_encoder - shared, don't delete
    'wan2.2_vae.safetensors',
    'wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors',
    'wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors',
    'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors',
    'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors',
  ],
  'wan2.2-t2v-a14b-hq': [
    // 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', // text_encoder - shared, don't delete
    'wan2.2_vae.safetensors',
    'wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors',
    'wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors',
  ],
  'wan2.2_ti2v_5B': [
    'wan2.2_ti2v_5B_fp16.safetensors',
    // 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', // text_encoder - shared, don't delete
    'wan2.2_vae.safetensors',
  ],
};

// Models that share files - uninstalling one should also uninstall the others
const SHARED_FILE_MODELS: Record<string, string[]> = {
  'wan2.2-t2v-a14b': ['wan2.2-t2v-a14b-hq'],
  'wan2.2-t2v-a14b-hq': ['wan2.2-t2v-a14b'],
};

async function findModelFiles(modelName: string): Promise<{ path: string; name: string; size: number; type: string }[]> {
  const modelsPath = getModelsPath();
  const foundFiles: { path: string; name: string; size: number; type: string }[] = [];
  
  // Note: text_encoders and clip are excluded because they are often shared between models
  const dirsToScan = [
    { dir: 'checkpoints', type: 'checkpoint' },
    { dir: 'diffusion_models', type: 'diffusion_model' },
    { dir: 'unet', type: 'unet' },
    { dir: 'vae', type: 'vae' },
    { dir: 'loras', type: 'lora' },
    // Excluded: 'clip' and 'text_encoders' - these are shared between models
  ];
  
  // Check if we have known file patterns for this model
  const knownFiles = MODEL_FILE_PATTERNS[modelName] || MODEL_FILE_PATTERNS[modelName.toLowerCase()];
  
  if (knownFiles && knownFiles.length > 0) {
    // Use exact file matching for known models
    for (const fileName of knownFiles) {
      for (const { dir, type } of dirsToScan) {
        try {
          const filePath = path.join(modelsPath, dir, fileName);
          const stats = await fs.stat(filePath);
          foundFiles.push({
            path: filePath,
            name: fileName,
            size: stats.size,
            type,
          });
          break; // Found in this dir, move to next file
        } catch (err) {
          // File not in this directory
        }
      }
    }
    return foundFiles;
  }
  
  // Fallback to fuzzy matching for other models
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

async function removeFromWorkflowFile(modelIds: string[]): Promise<{ removed: string[]; updated: boolean }> {
  const envPath = getEnvPath();
  const removed: string[] = [];
  
  try {
    let envContent = await fs.readFile(envPath, 'utf-8');
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    
    if (!workflowMatch || !workflowMatch[1]) {
      return { removed, updated: false };
    }
    
    let currentWorkflows = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
    const originalLength = currentWorkflows.length;
    
    // Build all variations for all model IDs
    const allVariations: string[] = [];
    for (const modelId of modelIds) {
      allVariations.push(
        modelId,
        `${modelId}.json`,
        modelId.toLowerCase(),
        `${modelId.toLowerCase()}.json`,
      );
    }
    
    currentWorkflows = currentWorkflows.filter(w => {
      const wLower = w.toLowerCase();
      const wNoJson = w.replace(/\.json$/, '').toLowerCase();
      const shouldRemove = allVariations.some(v => v.toLowerCase() === wLower || v.toLowerCase() === wNoJson);
      if (shouldRemove) {
        removed.push(w);
      }
      return !shouldRemove;
    });
    
    if (currentWorkflows.length !== originalLength) {
      const newWorkflowValue = currentWorkflows.join(',');
      envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newWorkflowValue}`);
      await fs.writeFile(envPath, envContent, 'utf-8');
      return { removed, updated: true };
    }
    
    return { removed, updated: false };
  } catch (err) {
    console.error('Error updating workflow file:', err);
    return { removed, updated: false };
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    // Support both single model_id and array of model_ids
    const modelIds: string[] = body.model_ids || (body.model_id ? [body.model_id] : []);
    
    if (modelIds.length === 0) {
      return NextResponse.json({
        success: false,
        error: 'Model ID(s) required'
      }, { status: 400 });
    }
    
    console.log(`Uninstalling models: ${modelIds.join(', ')}`);
    
    // Collect all affected models (including those that share files)
    const allAffectedModels = new Set<string>();
    for (const modelId of modelIds) {
      allAffectedModels.add(modelId);
      const relatedModels = SHARED_FILE_MODELS[modelId] || SHARED_FILE_MODELS[modelId.toLowerCase()] || [];
      relatedModels.forEach(m => allAffectedModels.add(m));
    }
    
    if (allAffectedModels.size > modelIds.length) {
      console.log(`Including related models: ${Array.from(allAffectedModels).join(', ')}`);
    }
    
    // Find and delete model files for all affected models
    const removedItems: { name: string; type: string; size: number }[] = [];
    const deletedPaths = new Set<string>(); // Track deleted paths to avoid duplicates
    
    for (const modelId of allAffectedModels) {
      const modelFiles = await findModelFiles(modelId);
      
      for (const file of modelFiles) {
        // Skip if already deleted (shared files between models)
        if (deletedPaths.has(file.path)) continue;
        
        try {
          await fs.unlink(file.path);
          deletedPaths.add(file.path);
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
    }
    
    // Remove from WORKFLOW_FILE - include all affected models
    const { removed: removedWorkflows, updated: workflowUpdated } = await removeFromWorkflowFile(Array.from(allAffectedModels));
    
    if (removedWorkflows.length > 0) {
      console.log(`Removed from WORKFLOW_FILE: ${removedWorkflows.join(', ')}`);
    }
    
    // Determine if restart is needed
    const requiresRestart = workflowUpdated || removedItems.length > 0;
    
    if (removedItems.length === 0 && !workflowUpdated) {
      return NextResponse.json({
        success: true,
        requires_restart: false,
        message: `No files found for ${modelIds.join(', ')}`,
        removed_items: [],
        affected_models: Array.from(allAffectedModels)
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
          await execAsync('docker restart comfy-bridge', { timeout: 60000 });
        }
      } catch (restartError) {
        console.error('Failed to restart container:', restartError);
      }
    }
    
    const affectedArray = Array.from(allAffectedModels);
    return NextResponse.json({
      success: true,
      requires_restart: requiresRestart,
      message: affectedArray.length > 1 
        ? `Uninstalled ${affectedArray.length} models: ${affectedArray.join(', ')}`
        : `Uninstalled ${affectedArray[0]}`,
      removed_items: removedItems,
      affected_models: affectedArray,
      removed_workflows: removedWorkflows
    });
    
  } catch (error: any) {
    console.error('Error uninstalling model:', error);
    return NextResponse.json({
      success: false,
      error: error.message || 'Failed to uninstall model'
    }, { status: 500 });
  }
}
