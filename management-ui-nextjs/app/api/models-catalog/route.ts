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
  capability_type: string;
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

function determineCapabilityType(modelId: string, modelInfo: any): string {
  const id = modelId.toLowerCase();
  const description = (modelInfo.description || '').toLowerCase();
  
  // Check for video models
  if (id.includes('video') || id.includes('t2v') || id.includes('i2v') || 
      description.includes('video') || description.includes('text-to-video') || 
      description.includes('image-to-video')) {
    if (id.includes('i2v') || description.includes('image-to-video')) {
      return 'Image-to-Video';
    }
    return 'Text-to-Video';
  }
  
  // Check for inpainting models
  if (id.includes('inpaint') || description.includes('inpainting')) {
    return 'Image-to-Image';
  }
  
  // Check for upscaling models
  if (id.includes('upscale') || id.includes('esrgan') || description.includes('upscaling')) {
    return 'Image-to-Image';
  }
  
  // Default to Text-to-Image for most models
  return 'Text-to-Image';
}

function estimateVramRequirement(model: ModelInfo): number {
  const baseline = model.baseline.toLowerCase();
  const name = model.name.toLowerCase();
  
  // Adjust based on capability type first
  let baseVram = 6; // Default for text-to-image
  
  if (model.capability_type === 'Text-to-Video') {
    baseVram = 12; // Video models need significantly more VRAM
  } else if (model.capability_type === 'Image-to-Video') {
    baseVram = 10; // Image-to-video models
  } else if (model.capability_type === 'Image-to-Image') {
    baseVram = 6; // Image-to-image models (inpainting, upscaling)
  }
  
  // More accurate VRAM estimation based on model architecture
  if (baseline.includes('wan')) {
    if (name.includes('a14b')) return 96; // 14B parameter models need high-end hardware
    if (name.includes('5b')) return Math.max(baseVram, 24); // 5B parameter models
    return Math.max(baseVram, 32); // Default Wan models
  }
  if (baseline.includes('flux')) {
    return Math.max(baseVram, 16); // Flux models are memory intensive
  }
  if (baseline.includes('stable_cascade')) {
    return Math.max(baseVram, 8); // Cascade is efficient
  }
  if (baseline.includes('stable_diffusion_xl') || baseline.includes('sdxl')) {
    return Math.max(baseVram, 8); // SDXL models
  }
  
  return baseVram; // Return the capability-based estimate
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
    
    // Check WORKFLOW_FILE for hosted models
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    
    if (workflowMatch && workflowMatch[1]) {
      const hostedModels = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
      return new Set(hostedModels);
    }
    
    return new Set();
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

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '25');
    const search = searchParams.get('search') || '';
    const styleFilter = searchParams.get('styleFilter') || 'all';
    const nsfwFilter = searchParams.get('nsfwFilter') || 'all';
    const sortField = searchParams.get('sortField') || 'name';
    const sortDirection = searchParams.get('sortDirection') || 'asc';
    
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
          style: modelInfo.style || 'generalist',
          homepage: '',
          nsfw: modelInfo.nsfw || false,
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
          vram_required_gb: estimateVramRequirement({
            baseline: modelInfo.baseline || 'stable_diffusion',
            name: modelId,
            type: modelInfo.type || 'checkpoints',
            inpainting: modelInfo.inpainting || false,
            description: modelInfo.description || '',
            version: modelInfo.version || '1.0',
            style: modelInfo.style || 'generalist',
            homepage: '',
            nsfw: modelInfo.nsfw || false,
            download_all: false,
            capability_type: determineCapabilityType(modelId, modelInfo),
            requirements: {},
            config: { files: [], download: [] },
            features_not_supported: [],
            size_on_disk_bytes: modelInfo.size_mb ? modelInfo.size_mb * 1024 * 1024 : 0
          }),
          requires_huggingface_key: modelInfo.url?.includes('huggingface.co') || false,
          requires_civitai_key: modelInfo.url?.includes('civitai.com') || false,
          download_source: modelInfo.url?.includes('huggingface.co') ? 'huggingface' : 
                          modelInfo.url?.includes('civitai.com') ? 'civitai' : 'other',
          installed: false, // Will be checked below
          hosting: hostedModels.has(modelId),
          capability_type: determineCapabilityType(modelId, modelInfo)
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
    
    // Apply filters
    let filteredModels = enhancedModels;
    
    // Apply search filter (only on model name)
    if (search) {
      const searchLower = search.toLowerCase();
      filteredModels = filteredModels.filter(model => 
        model.name.toLowerCase().includes(searchLower)
      );
    }
    
    // Apply style filter
    if (styleFilter !== 'all') {
      filteredModels = filteredModels.filter(model => {
        if (styleFilter === 'text-to-image' && model.capability_type !== 'Text-to-Image') return false;
        if (styleFilter === 'text-to-video' && model.capability_type !== 'Text-to-Video') return false;
        if (styleFilter === 'image-to-video' && model.capability_type !== 'Image-to-Video') return false;
        if (styleFilter === 'image-to-image' && model.capability_type !== 'Image-to-Image') return false;
        if (styleFilter === 'anime' && model.style !== 'anime') return false;
        if (styleFilter === 'realistic' && model.style !== 'realistic') return false;
        if (styleFilter === 'generalist' && model.style !== 'generalist') return false;
        if (styleFilter === 'artistic' && model.style !== 'artistic') return false;
        if (styleFilter === 'video' && model.style !== 'video') return false;
        return true;
      });
    }
    
    // Apply NSFW filter
    if (nsfwFilter !== 'all') {
      filteredModels = filteredModels.filter(model => {
        if (nsfwFilter === 'nsfw-only' && !model.nsfw) return false;
        if (nsfwFilter === 'sfw-only' && model.nsfw) return false;
        return true;
      });
    }
    
    // Sort models
    filteredModels.sort((a: any, b: any) => {
      let aValue = a[sortField];
      let bValue = b[sortField];
      
      // Handle different data types
      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }
      
      if (sortDirection === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });
    
    // Calculate pagination
    const totalCount = filteredModels.length;
    const totalPages = Math.ceil(totalCount / limit);
    const startIndex = (page - 1) * limit;
    const endIndex = startIndex + limit;
    const paginatedModels = filteredModels.slice(startIndex, endIndex);
    
    return NextResponse.json({ 
      models: paginatedModels,
      total_count: totalCount,
      installed_count: installedCount,
      pagination: {
        page,
        limit,
        total_pages: totalPages,
        has_next: page < totalPages,
        has_prev: page > 1
      }
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