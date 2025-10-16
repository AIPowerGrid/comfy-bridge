import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';

interface ModelConfig {
  url: string;
  filename: string;
  type: string;
  size_mb?: number;
  sha256?: string | null;
  inpainting?: boolean;
  dependencies?: Array<{
    type: string;
    filename: string;
    url: string;
    size_mb?: number;
  }>;
}

function estimateVramRequirement(modelName: string, sizeGb: number): number {
  const lowerName = modelName.toLowerCase();
  
  // Wan2.2 video models (large disk size but moderate VRAM requirement)
  if (lowerName.includes('wan2.2-t2v-a14b') || lowerName.includes('wan2_2_t2v_14b')) return 24;
  if (lowerName.includes('wan2.2_ti2v_5b') || lowerName.includes('wan2_2_ti2v_5b')) return 12;
  
  // Other models
  if (lowerName.includes('flux')) return 12;
  if (lowerName.includes('sdxl') || lowerName.includes('xl')) return 8;
  if (lowerName.includes('sd3')) return 10;
  if (sizeGb > 10) return 12;
  if (sizeGb > 5) return 8;
  return 6;
}

function categorizeModel(modelName: string): string {
  const lowerName = modelName.toLowerCase();
  
  if (lowerName.includes('flux')) return 'Flux';
  if (lowerName.includes('sdxl') || lowerName.includes('xl')) return 'Stable Diffusion XL';
  if (lowerName.includes('sd3')) return 'Stable Diffusion 3';
  if (lowerName.includes('turbo')) return 'Turbo';
  return 'Stable Diffusion';
}

function getCapabilityType(modelName: string, config: ModelConfig): string {
  const lowerName = modelName.toLowerCase();
  
  // Video models
  if (lowerName.includes('wan2.2_ti2v_5b') || lowerName.includes('wan2_2_ti2v_5b')) {
    return 'Text-to-Video, Image-to-Video'; // Supports both
  }
  if (lowerName.includes('wan2.2-t2v-a14b') || lowerName.includes('wan2_2_t2v_14b')) {
    return 'Text-to-Video';
  }
  if (lowerName.includes('ti2v') || lowerName.includes('image-to-video')) {
    return 'Image-to-Video';
  }
  if (lowerName.includes('t2v') || lowerName.includes('text-to-video')) {
    return 'Text-to-Video';
  }
  
  // Image models
  if (lowerName.includes('inpainting') || config.inpainting) {
    return 'Image-to-Image';
  }
  
  return 'Text-to-Image';
}

function generateDescription(modelName: string): string {
  const descriptions: Record<string, string> = {
    'Flux.1-Krea-dev Uncensored (fp8+CLIP+VAE)': 'Advanced Flux model with CLIP and VAE. High quality, uncensored outputs.',
    'sdxl': 'Stable Diffusion XL base model. High resolution, versatile.',
    'stable_diffusion': 'Classic Stable Diffusion 1.5. Fast, reliable, lower VRAM.',
  };
  return descriptions[modelName] || `${modelName} model for image generation`;
}

async function getInstalledModels(): Promise<string[]> {
  try {
    const modelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';
    const checkpointsPath = path.join(modelsPath, 'checkpoints');
    
    const files = await fs.readdir(checkpointsPath);
    return files
      .filter(file => file.endsWith('.safetensors'))
      .map(file => path.basename(file, '.safetensors'));
  } catch (error) {
    return [];
  }
}

async function getSelectedModels(): Promise<string[]> {
  try {
    const envPath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    const content = await fs.readFile(envPath, 'utf-8');
    
    for (const line of content.split('\n')) {
      if (line.startsWith('GRID_MODEL=')) {
        const value = line.split('=')[1].split('#')[0].trim();
        if (value) {
          return value.split(',').map(m => m.trim());
        }
      }
    }
  } catch (error) {
    console.error('Error reading selected models:', error);
  }
  return [];
}

export async function GET() {
  try {
    const configPath = process.env.MODEL_CONFIGS_PATH || '/app/comfy-bridge/model_configs.json';
    const configContent = await fs.readFile(configPath, 'utf-8');
    const configs: Record<string, ModelConfig> = JSON.parse(configContent);
    
    const installed = await getInstalledModels();
    const selected = await getSelectedModels();
    
    const enhanced: Record<string, any> = {};
    
    for (const [modelName, config] of Object.entries(configs)) {
      const sizeGb = (config.size_mb || 0) / 1024; // Convert MB to GB
      let depSizeGb = 0;
      
      if (config.dependencies) {
        depSizeGb = config.dependencies.reduce((sum, dep) => {
          return sum + ((dep.size_mb || 0) / 1024); // Convert MB to GB
        }, 0);
      }
      
      const totalSizeGb = sizeGb + depSizeGb;
      
      enhanced[modelName] = {
        ...config,
        display_name: modelName,
        size_gb: Math.round(totalSizeGb * 100) / 100,
        vram_required_gb: estimateVramRequirement(modelName, totalSizeGb),
        category: categorizeModel(modelName),
        capability_type: getCapabilityType(modelName, config),
        description: (config as any).description || generateDescription(modelName),
        installed: installed.includes(modelName),
        selected: selected.includes(modelName),
      };
    }
    
    return NextResponse.json(enhanced);
  } catch (error) {
    console.error('Error loading models:', error);
    return NextResponse.json({ error: 'Failed to load models' }, { status: 500 });
  }
}

