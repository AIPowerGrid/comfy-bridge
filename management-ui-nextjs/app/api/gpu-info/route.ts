import { NextResponse } from 'next/server';
import { loadModelsData } from '../models/models-service';

// Force dynamic rendering - don't cache this route
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // Call the GPU info server running on the comfy-bridge container
    const response = await fetch('http://comfy-bridge:8001/gpu-info');
    const gpuInfo = await response.json();
    
    // Get installed models to calculate VRAM usage
    let modelsData: Record<string, any> = {};
    try {
      modelsData = await loadModelsData();
    } catch (error) {
      console.warn('Could not fetch models data:', error);
    }
    
    // Calculate VRAM used by installed models
    let vramUsedGb = 0;
    const modelEntries = modelsData?.models
      ? Object.values(modelsData.models)
      : Object.values(modelsData || {});
    
    for (const model of modelEntries as any[]) {
      if (model && typeof model === 'object' && model.installed) {
        vramUsedGb += model.vram_required_gb || 0;
      }
    }
    
    // Add VRAM usage to each GPU
    const gpusWithUsage = gpuInfo.gpus.map((gpu: any) => ({
      ...gpu,
      vram_used_gb: vramUsedGb,
      vram_available_gb: Math.round((gpu.memory_gb - vramUsedGb) * 10) / 10,
      vram_percent_used: Math.round((vramUsedGb / gpu.memory_gb) * 100),
    }));
    
    return NextResponse.json({
      ...gpuInfo,
      gpus: gpusWithUsage,
      total_vram_used_gb: vramUsedGb,
    });
  } catch (error: any) {
    console.error('GPU detection failed:', error.message);
    return NextResponse.json({
      available: false,
      gpus: [],
      total_memory_gb: 0,
    });
  }
}

