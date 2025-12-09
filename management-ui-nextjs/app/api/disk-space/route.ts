import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

// Force dynamic rendering
export const dynamic = 'force-dynamic';

// Check if running in Docker or locally
const isWindows = process.platform === 'win32';
const isLocalDev = isWindows || !process.env.DOCKER_CONTAINER;

// Get the models path for Windows
function getWindowsModelsPath() {
  return process.env.MODELS_PATH || 'C:\\dev\\comfy-bridge\\persistent_volumes\\models';
}

// Recursively scan a directory for model files
async function scanDirectoryForModels(dirPath: string, prefix: string = ''): Promise<string[]> {
  const models: string[] = [];
  
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      
      if (entry.isDirectory()) {
        // Recursively scan subdirectories
        const subModels = await scanDirectoryForModels(fullPath, prefix ? `${prefix}/${entry.name}` : entry.name);
        models.push(...subModels);
      } else if (entry.isFile()) {
        const ext = entry.name.toLowerCase();
        if (ext.endsWith('.safetensors') || ext.endsWith('.ckpt') || ext.endsWith('.pth') || ext.endsWith('.bin') || ext.endsWith('.gguf')) {
          models.push(prefix ? `${prefix}/${entry.name}` : entry.name);
        }
      }
    }
  } catch (err) {
    // Directory might not exist or not accessible
    console.log(`Could not scan ${dirPath}:`, err);
  }
  
  return models;
}

// Scan for model files on Windows
async function scanWindowsModels(modelsPath: string): Promise<string[]> {
  console.log('Scanning for models in:', modelsPath);
  const models = await scanDirectoryForModels(modelsPath);
  console.log(`Found ${models.length} model files`);
  return models;
}

// Get disk space on Windows using PowerShell (wmic is deprecated in Windows 11)
async function getWindowsDiskSpace(targetPath: string) {
  const modelsPath = getWindowsModelsPath();
  const models = await scanWindowsModels(modelsPath).catch(() => []);
  
  try {
    // Get the drive letter from the path
    const driveLetter = path.parse(targetPath).root.replace(/\\/g, '').replace(':', '');
    
    // Use PowerShell Get-CimInstance (replacement for wmic)
    const { stdout } = await execAsync(
      `powershell -NoProfile -Command "Get-CimInstance -ClassName Win32_LogicalDisk -Filter \\"DeviceID='${driveLetter}:'\\" | Select-Object Size,FreeSpace | ConvertTo-Json"`,
      { shell: 'cmd.exe' }
    );
    
    const diskInfo = JSON.parse(stdout.trim());
    const totalBytes = diskInfo.Size;
    const freeBytes = diskInfo.FreeSpace;
    const usedBytes = totalBytes - freeBytes;
    
    return {
      name: `${driveLetter}:`,
      display_name: `AI Models Volume (${driveLetter}:)`,
      mount_point: 'persistent_volumes/models',
      total_gb: Math.round((totalBytes / (1024 * 1024 * 1024)) * 100) / 100,
      used_gb: Math.round((usedBytes / (1024 * 1024 * 1024)) * 100) / 100,
      free_gb: Math.round((freeBytes / (1024 * 1024 * 1024)) * 100) / 100,
      percent_used: Math.round((usedBytes / totalBytes) * 100 * 10) / 10,
      models_count: models.length,
      models: models,
    };
  } catch (error) {
    console.error('Windows disk space check failed:', error);
    // Fallback: return basic info with model scan
    return {
      name: 'C:',
      display_name: 'AI Models Volume',
      mount_point: 'persistent_volumes/models',
      total_gb: 0,
      used_gb: 0,
      free_gb: 0,
      percent_used: 0,
      models_count: models.length,
      models: models,
      error: 'Could not get disk space info',
    };
  }
}

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

// Get the display path for the models directory
function getModelsDisplayPath(): string {
  if (isWindows) {
    return process.env.MODELS_PATH || 'persistent_volumes/models';
  }
  // In Docker, show the host path for clarity
  return 'persistent_volumes/models';
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
  // Get real disk space on Windows
  if (isWindows) {
    // Use the comfy-bridge directory for disk info
    const localPath = process.env.MODELS_PATH || 'c:\\dev\\comfy-bridge';
    const diskInfo = await getWindowsDiskSpace(localPath);
    return NextResponse.json(diskInfo);
  }

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
        mount_point: getModelsDisplayPath(),
        total_gb: Math.round(totalKb / (1024 * 1024) * 100) / 100,
        used_gb: Math.round(usedKb / (1024 * 1024) * 100) / 100,
        free_gb: Math.round(availKb / (1024 * 1024) * 100) / 100,
        percent_used: Math.round((usedKb / totalKb) * 100 * 10) / 10,
        models_count: allModels.length,
        models: allModels,
      });
    }
    
    return NextResponse.json({ error: 'Failed to parse disk info' }, { status: 500 });
  } catch (error: any) {
    console.error('Disk space check failed:', error);
    return NextResponse.json({ error: 'Disk space check failed: ' + error.message }, { status: 500 });
  }
}

