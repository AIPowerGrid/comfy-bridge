import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Force dynamic rendering - don't cache this route
export const dynamic = 'force-dynamic';

// Get GPU info using nvidia-smi (works in Docker with GPU access)
async function getNvidiaSmiGpuInfo() {
  try {
    const { stdout } = await execAsync('nvidia-smi --query-gpu=name,memory.total,driver_version,memory.used,memory.free --format=csv,noheader,nounits', {
      timeout: 10000,
    });
    const lines = stdout.trim().split('\n').filter(line => line.trim());
    
    if (lines.length === 0) {
      throw new Error('No GPU data returned from nvidia-smi');
    }
    
    const gpus = lines.map((line) => {
      const parts = line.split(',').map(p => p.trim());
      const totalMemoryMb = parseFloat(parts[1]) || 0;
      const usedMemoryMb = parseFloat(parts[3]) || 0;
      const freeMemoryMb = parseFloat(parts[4]) || 0;
      const memoryGb = totalMemoryMb / 1024;
      const usedGb = usedMemoryMb / 1024;
      const freeGb = freeMemoryMb / 1024;
      
      return {
        name: parts[0],
        memory_gb: Math.ceil(memoryGb),
        driver_version: parts[2],
        vram_used_gb: Math.round(usedGb * 10) / 10,
        vram_available_gb: Math.round(freeGb * 10) / 10,
        vram_percent_used: totalMemoryMb > 0 ? Math.round((usedMemoryMb / totalMemoryMb) * 100) : 0,
      };
    });
    
    const totalMemory = gpus.reduce((sum, gpu) => sum + gpu.memory_gb, 0);
    const totalUsed = gpus.reduce((sum, gpu) => sum + (gpu.vram_used_gb || 0), 0);
    
    return {
      available: true,
      gpus,
      total_memory_gb: totalMemory,
      total_vram_used_gb: Math.round(totalUsed * 10) / 10,
    };
  } catch (error: any) {
    console.error('nvidia-smi failed:', error.message);
    return null;
  }
}

// Get GPU info from comfy-bridge API (primary method in Docker)
async function getComfyBridgeGpuInfo() {
  // Try multiple URLs in case of network issues
  const urls = [
    'http://comfy-bridge:8001/gpu-info',
    'http://localhost:8001/gpu-info',
  ];
  
  for (const url of urls) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { 'Accept': 'application/json' },
      });
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        console.error(`GPU API ${url} returned HTTP ${response.status}`);
        continue;
      }
      
      const gpuInfo = await response.json();
      
      // Round up memory to whole numbers
      const gpusRounded = (gpuInfo.gpus || []).map((gpu: any) => ({
        name: gpu.name,
        memory_gb: Math.ceil(gpu.memory_gb || 0),
        driver_version: gpu.driver_version,
        vram_used_gb: gpu.vram_used_gb,
        vram_available_gb: gpu.vram_available_gb,
        vram_percent_used: gpu.vram_percent_used,
      }));
      
      console.log(`GPU info from ${url}: ${gpusRounded.length} GPU(s)`);
      
      return {
        available: gpuInfo.available,
        gpus: gpusRounded,
        total_memory_gb: gpusRounded.reduce((sum: number, gpu: any) => sum + gpu.memory_gb, 0),
        total_vram_used_gb: gpuInfo.total_vram_used_gb,
      };
    } catch (error: any) {
      console.error(`GPU API ${url} failed:`, error.message);
    }
  }
  
  return null;
}

export async function GET() {
  // Try comfy-bridge API first (most reliable when running in Docker)
  let gpuInfo = await getComfyBridgeGpuInfo();
  
  if (gpuInfo && gpuInfo.available) {
    console.log('GPU info from comfy-bridge API:', gpuInfo.gpus?.length || 0, 'GPU(s)');
    return NextResponse.json(gpuInfo);
  }
  
  // Fallback to nvidia-smi (works on Windows or if nvidia-smi is available)
  gpuInfo = await getNvidiaSmiGpuInfo();
  
  if (gpuInfo) {
    console.log('GPU info from nvidia-smi:', gpuInfo.gpus.length, 'GPU(s)');
    return NextResponse.json(gpuInfo);
  }
  
  // No GPU detected
  console.log('No GPU detected via comfy-bridge API or nvidia-smi');
  return NextResponse.json({
    available: false,
    gpus: [],
    total_memory_gb: 0,
    error: 'GPU detection failed. The comfy-bridge container may not be running.',
  });
}

