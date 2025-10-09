import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

// Force dynamic rendering
export const dynamic = 'force-dynamic';

interface DriveInfo {
  name: string;
  display_name: string;
  mount_point: string;
  host_path?: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent_used: number;
  models_count: number;
  models: string[];
}

function getVolumeDisplayName(mountPoint: string): { displayName: string; hostPath?: string } {
  // Map container paths to user-friendly names
  const volumeMap: { [key: string]: string } = {
    '/app/ComfyUI/models': 'AI Models Volume',
    '/app/ComfyUI/output': 'Generated Images',
    '/app/ComfyUI/input': 'Input Images',
    '/app/comfy-bridge/.cache': 'Cache & Metadata',
    '/': 'System Volume',
  };
  
  // Check if this is a known volume
  for (const [path, name] of Object.entries(volumeMap)) {
    if (mountPoint === path || mountPoint.startsWith(path + '/')) {
      return { displayName: name };
    }
  }
  
  // For unknown mounts, use the mount point
  return { displayName: mountPoint };
}

async function getModelsByPath(modelsPath: string): Promise<{ [key: string]: string[] }> {
  const modelsByDrive: { [key: string]: string[] } = {};
  
  try {
    const modelTypes = ['checkpoints', 'vae', 'clip', 'loras', 'unet', 'diffusion_models'];
    
    for (const modelType of modelTypes) {
      const typePath = path.join(modelsPath, modelType);
      try {
        const files = await fs.readdir(typePath);
        for (const file of files) {
          if (file.endsWith('.safetensors') || file.endsWith('.ckpt') || file.endsWith('.pth')) {
            const fullPath = path.join(typePath, file);
            // Get the mount point for this file
            const { stdout } = await execAsync(`df -P "${fullPath}" | tail -1 | awk '{print $6}'`);
            const mountPoint = stdout.trim();
            
            if (!modelsByDrive[mountPoint]) {
              modelsByDrive[mountPoint] = [];
            }
            modelsByDrive[mountPoint].push(`${modelType}/${file}`);
          }
        }
      } catch (err) {
        // Directory might not exist, skip
      }
    }
  } catch (error) {
    console.error('Error scanning models:', error);
  }
  
  return modelsByDrive;
}

export async function GET() {
  try {
    const modelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';
    
    // Get disk info for the models volume only
    const { stdout } = await execAsync(`df -k "${modelsPath}" | tail -1`);
    const parts = stdout.trim().split(/\s+/);
    
    if (parts.length >= 6) {
      const device = parts[0];
      const totalKb = parseInt(parts[1]);
      const usedKb = parseInt(parts[2]);
      const availKb = parseInt(parts[3]);
      
      // Get models in the volume
      const modelsByDrive = await getModelsByPath(modelsPath);
      const allModels = Object.values(modelsByDrive).flat();
      
      return NextResponse.json({
        name: device,
        display_name: 'AI Models Volume',
        mount_point: modelsPath,
        total_gb: Math.round(totalKb / (1024 * 1024) * 100) / 100,
        used_gb: Math.round(usedKb / (1024 * 1024) * 100) / 100,
        free_gb: Math.round(availKb / (1024 * 1024) * 100) / 100,
        percent_used: Math.round((usedKb / totalKb) * 100 * 10) / 10,
        models_count: allModels.length,
        models: allModels,
      });
    }
    
    return NextResponse.json({ error: 'Failed to get disk space' }, { status: 500 });
  } catch (error) {
    console.error('Disk space check failed:', error);
    return NextResponse.json({ error: 'Failed to get disk space' }, { status: 500 });
  }
}

