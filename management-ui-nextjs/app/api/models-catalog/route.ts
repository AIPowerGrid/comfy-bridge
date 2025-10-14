import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';

export const dynamic = 'force-dynamic';

interface ModelFile {
  path: string;
  file_name?: string;
  file_url?: string;
  file_path?: string;
  sha256sum?: string;
  md5sum?: string;
  file_type?: string;
}

interface ModelConfig {
  files: ModelFile[];
  download?: Array<{
    file_name: string;
    file_path: string;
    file_url: string;
  }>;
  download_url?: string; // For single file downloads
}

interface ModelInfo {
  name: string;
  baseline: string;
  type: string;
  inpainting: boolean;
  description: string;
  version: string;
  style: string;
  homepage?: string;
  nsfw: boolean;
  download_all: boolean;
  requirements?: {
    min_steps?: number;
    max_steps?: number;
    min_cfg_scale?: number;
    max_cfg_scale?: number;
    clip_skip?: number;
    samplers?: string[];
    schedulers?: string[];
  };
  config: ModelConfig;
  features_not_supported?: string[];
  size_on_disk_bytes?: number;
}

interface EnhancedModel extends ModelInfo {
  id: string;
  display_name: string;
  size_gb: number;
  vram_required_gb: number;
  requires_huggingface_key: boolean;
  requires_civitai_key: boolean;
  download_source: 'huggingface' | 'civitai' | 'other';
  installed: boolean;
  hosting: boolean;
  capability_type: string;
}

function getCapabilityType(model: ModelInfo): string {
  const style = model.style?.toLowerCase() || '';
  const baseline = model.baseline?.toLowerCase() || '';
  const desc = model.description?.toLowerCase() || '';
  const inpainting = model.inpainting;
  
  // Video models
  if (style.includes('video') || baseline.includes('wan')) {
    if (inpainting || desc.includes('image-to-video') || desc.includes('image to video')) {
      return 'Image-to-Video';
    }
    return 'Text-to-Video';
  }
  
  // Image models
  if (inpainting || desc.includes('image-to-image') || desc.includes('img2img')) {
    return 'Image-to-Image';
  }
  
  return 'Text-to-Image';
}

function estimateVramRequirement(model: ModelInfo): number {
  const baseline = model.baseline.toLowerCase();
  const name = model.name.toLowerCase();
  
  // More accurate VRAM estimation based on model architecture
  if (baseline.includes('wan')) {
    if (name.includes('a14b')) return 96; // 14B parameter models need high-end hardware
    if (name.includes('5b')) return 24; // 5B parameter models
    return 32; // Default Wan models
  }
  if (baseline.includes('flux')) {
    return 16; // Flux models are memory intensive
  }
  if (baseline.includes('stable_cascade')) {
    return 8; // Cascade is efficient
  }
  if (baseline.includes('stable_diffusion_xl') || baseline.includes('sdxl')) {
    return 8; // SDXL models
  }
  
  return 6; // Default for SD 1.x models
}

function detectDownloadSource(model: ModelInfo): { source: 'huggingface' | 'civitai' | 'other'; requiresHuggingface: boolean; requiresCivitai: boolean } {
  const downloads = model.config.download || [];
  const downloadUrl = model.config.download_url;
  const urls = [...downloads.map(d => d.file_url), downloadUrl].filter(Boolean);
  
  let hasHuggingface = false;
  let hasCivitai = false;
  
  for (const url of urls) {
    if (url && url.includes('huggingface.co')) {
      hasHuggingface = true;
    } else if (url && url.includes('civitai.com')) {
      hasCivitai = true;
    }
  }
  
  if (hasHuggingface && hasCivitai) {
    return { source: 'other', requiresHuggingface: true, requiresCivitai: true };
  } else if (hasHuggingface) {
    return { source: 'huggingface', requiresHuggingface: true, requiresCivitai: false };
  } else if (hasCivitai) {
    return { source: 'civitai', requiresHuggingface: false, requiresCivitai: true };
  } else {
    return { source: 'other', requiresHuggingface: false, requiresCivitai: false };
  }
}

async function getHostedModels(): Promise<Set<string>> {
  try {
    const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    const envContent = await fs.readFile(envFilePath, 'utf-8');
    const match = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    if (match && match[1]) {
      return new Set(match[1].split(',').map(s => s.trim()).filter(Boolean));
    }
  } catch (error) {
    console.error('Error reading .env for hosted models:', error);
  }
  return new Set();
}

async function checkModelInstalled(modelId: string, files: ModelFile[], modelsPath: string): Promise<boolean> {
  try {
    if (!files || files.length === 0) {
      return false; // No files to check
    }
    
    for (const file of files) {
      if (!file.path) {
        continue; // Skip files without paths
      }
      
      const fileName = path.basename(file.path);
      
      // Check in all possible directories based on file type
      const possiblePaths = [
        path.join(modelsPath, 'checkpoints', fileName),
        path.join(modelsPath, 'diffusion_models', fileName),
        path.join(modelsPath, 'unet', fileName),
        path.join(modelsPath, 'vae', fileName),
        path.join(modelsPath, 'clip', fileName),
        path.join(modelsPath, 'text_encoders', fileName),
        path.join(modelsPath, 'loras', fileName),
      ];
      
      let found = false;
      for (const filePath of possiblePaths) {
        try {
          await fs.access(filePath);
          found = true;
          break;
        } catch (err) {
          // File doesn't exist at this path, continue
        }
      }
      
      if (!found) {
        return false; // If any file is missing, model is not installed
      }
    }
    return true; // All files found
  } catch (error) {
    console.error(`Error checking model ${modelId}:`, error);
    return false;
  }
}

export async function GET() {
  try {
    const modelsFilePath = '/app/comfy-bridge/model_configs.json';
    const comfyUIModelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';

    // Check if catalog file exists, if not trigger a sync
    try {
      await fs.access(modelsFilePath);
    } catch (error) {
      console.log('Catalog file not found, triggering sync...');
      try {
        const { exec } = await import('child_process');
        const { promisify } = await import('util');
        const execAsync = promisify(exec);
        await execAsync('python3 /app/comfy-bridge/catalog_sync.py', { timeout: 30000 });
      } catch (syncError) {
        console.error('Failed to sync catalog:', syncError);
        return NextResponse.json({ 
          error: 'Catalog not available and sync failed', 
          message: 'Please try again in a few moments',
          models: [],
          total_count: 0,
          installed_count: 0,
        }, { status: 503 });
      }
    }

    const data = await fs.readFile(modelsFilePath, 'utf-8');
    const rawModels: Record<string, any> = JSON.parse(data);

    // Get currently hosted models from WORKFLOW_FILE
    const hostedModels = await getHostedModels();
    
    const enhancedModels: EnhancedModel[] = [];
    let installedCount = 0;
    
    for (const [modelId, modelInfo] of Object.entries(rawModels)) {
      try {
        // Convert simple catalog format to enhanced format
        const enhancedModel: EnhancedModel = {
          id: modelId,
          name: modelId.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          baseline: modelInfo.type || 'stable_diffusion',
          type: modelInfo.type || 'checkpoints',
          inpainting: false,
          description: modelInfo.description || '',
          version: '1.0',
          style: 'generalist',
          homepage: '',
          nsfw: false,
          download_all: false,
          requirements: {},
          config: {
            files: [{
              path: modelInfo.filename,
              file_type: modelInfo.type || 'checkpoints'
            }],
            download_url: modelInfo.url
          },
          features_not_supported: [],
          size_on_disk_bytes: modelInfo.size_mb ? modelInfo.size_mb * 1024 * 1024 : 0,
          display_name: modelId.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          size_gb: modelInfo.size_mb ? Math.round((modelInfo.size_mb / 1024) * 100) / 100 : 0,
          vram_required_gb: modelInfo.size_mb ? Math.ceil(modelInfo.size_mb / 1000) : 8,
          requires_huggingface_key: modelInfo.url?.includes('huggingface.co') || false,
          requires_civitai_key: modelInfo.url?.includes('civitai.com') || false,
          download_source: modelInfo.url?.includes('huggingface.co') ? 'huggingface' : 
                          modelInfo.url?.includes('civitai.com') ? 'civitai' : 'other',
          installed: false, // Will be checked below
          hosting: hostedModels.has(modelId),
          capability_type: 'Text-to-Image' // Default, could be enhanced based on model name
        };

        // Check if model is installed
        const installed = await checkModelInstalled(modelId, enhancedModel.config.files, comfyUIModelsPath);
        enhancedModel.installed = installed;
        
        if (installed) {
          installedCount++;
        }
        
        enhancedModels.push(enhancedModel);
      } catch (error) {
        console.error(`Error processing model ${modelId}:`, error);
        // Skip this model if there's an error
        continue;
      }
    }
    
    // Sort by type, then by name
    enhancedModels.sort((a, b) => {
      if (a.type !== b.type) {
        return a.type.localeCompare(b.type);
      }
      return a.name.localeCompare(b.name);
    });
    
    return NextResponse.json({ 
      models: enhancedModels,
      total_count: enhancedModels.length,
      installed_count: installedCount,
    });
  } catch (error: any) {
    console.error('Failed to load model catalog:', error);
    return NextResponse.json({ 
      error: 'Failed to load model catalog', 
      message: error.message,
      models: [],
      total_count: 0,
      installed_count: 0,
    }, { status: 500 });
  }
}