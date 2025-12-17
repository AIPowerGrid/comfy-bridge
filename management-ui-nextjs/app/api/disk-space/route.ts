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

// Get all available drives on Windows (fixed drives only, type 3)
async function getWindowsDrives(): Promise<string[]> {
  try {
    // Get all fixed drives (DriveType 3) - includes HDD, SSD, NVMe
    const { stdout } = await execAsync(
      `powershell -NoProfile -Command "Get-CimInstance -ClassName Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } | ForEach-Object { $_.DeviceID }"`,
      { shell: 'cmd.exe', timeout: 10000 }
    );
    
    const drives = stdout.trim().split(/\r?\n/).map(d => d.trim()).filter(d => /^[A-Z]:$/i.test(d));
    console.log('Found Windows fixed drives:', drives);
    
    if (drives.length === 0) {
      // Fallback: try to get all drives including removable
      const { stdout: fallbackOut } = await execAsync(
        `powershell -NoProfile -Command "Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -ne $null } | ForEach-Object { $_.Name + ':' }"`,
        { shell: 'cmd.exe', timeout: 10000 }
      );
      const fallbackDrives = fallbackOut.trim().split(/\r?\n/).map(d => d.trim()).filter(d => /^[A-Z]:$/i.test(d));
      console.log('Fallback drives found:', fallbackDrives);
      return fallbackDrives.length > 0 ? fallbackDrives : ['C:'];
    }
    
    return drives;
  } catch (error) {
    console.error('Failed to get Windows drives:', error);
    // Ultimate fallback - scan common drive letters
    const commonDrives: string[] = [];
    for (const letter of 'CDEFGHIJKLMNOPQRSTUVWXYZ') {
      try {
        await fs.access(`${letter}:\\`);
        commonDrives.push(`${letter}:`);
      } catch {
        // Drive doesn't exist
      }
    }
    console.log('Manual drive scan found:', commonDrives);
    return commonDrives.length > 0 ? commonDrives : ['C:'];
  }
}

// Get the models path for Windows - check all drives
function getWindowsModelsPath() {
  return process.env.MODELS_PATH || 'C:\\dev\\comfy-bridge\\persistent_volumes\\models';
}

// Recursively scan a directory for model files, returning full paths with drive letter
async function scanDirectoryForModels(dirPath: string, rootPath: string): Promise<string[]> {
  const models: string[] = [];
  
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      
      if (entry.isDirectory()) {
        // Recursively scan subdirectories
        const subModels = await scanDirectoryForModels(fullPath, rootPath);
        models.push(...subModels);
      } else if (entry.isFile()) {
        const ext = entry.name.toLowerCase();
        if (ext.endsWith('.safetensors') || ext.endsWith('.ckpt') || ext.endsWith('.pth') || ext.endsWith('.bin') || ext.endsWith('.gguf')) {
          // Return full absolute path with drive letter (e.g., "C:\dev\ComfyUI\models\checkpoints\model.safetensors")
          models.push(fullPath);
        }
      }
    }
  } catch (err) {
    // Directory might not exist or not accessible
  }
  
  return models;
}

// Scan common locations on a Windows drive for model files
async function scanWindowsDriveForModels(driveLetter: string): Promise<string[]> {
  const allModels: string[] = [];
  
  // Common locations to look for models
  const searchPaths = [
    `${driveLetter}\\ComfyUI\\models`,
    `${driveLetter}\\dev\\ComfyUI\\models`,
    `${driveLetter}\\dev\\comfy-bridge\\persistent_volumes\\models`,
    `${driveLetter}\\comfy-bridge\\persistent_volumes\\models`,
    `${driveLetter}\\AI\\models`,
    `${driveLetter}\\Models`,
    `${driveLetter}\\stable-diffusion\\models`,
  ];
  
  // Add custom MODELS_PATH if set
  const customPath = process.env.MODELS_PATH;
  if (customPath && customPath.toUpperCase().startsWith(driveLetter.toUpperCase())) {
    searchPaths.unshift(customPath);
  }
  
  for (const searchPath of searchPaths) {
    try {
      await fs.access(searchPath);
      console.log(`Scanning ${searchPath} for models...`);
      const models = await scanDirectoryForModels(searchPath, searchPath);
      allModels.push(...models);
    } catch {
      // Path doesn't exist, skip
    }
  }
  
  return allModels;
}

// Get disk space for a specific Windows drive
async function getWindowsDriveInfo(driveLetter: string): Promise<DriveInfo | null> {
  try {
    const driveId = driveLetter.replace(':', '');
    
    // Use PowerShell Get-CimInstance (replacement for wmic)
    const { stdout } = await execAsync(
      `powershell -NoProfile -Command "Get-CimInstance -ClassName Win32_LogicalDisk -Filter \\"DeviceID='${driveId}:'\\" | Select-Object Size,FreeSpace,VolumeName | ConvertTo-Json"`,
      { shell: 'cmd.exe' }
    );
    
    const diskInfo = JSON.parse(stdout.trim());
    
    if (!diskInfo || !diskInfo.Size) {
      return null;
    }
    
    const totalBytes = diskInfo.Size;
    const freeBytes = diskInfo.FreeSpace;
    const usedBytes = totalBytes - freeBytes;
    const volumeName = diskInfo.VolumeName || `Local Disk`;
    
    // Scan for model files on this drive
    const models = await scanWindowsDriveForModels(`${driveId}:`);
    
    return {
      name: `${driveId}:`,
      display_name: `${volumeName} (${driveId}:)`,
      mount_point: `${driveId}:\\`,
      total_gb: Math.round((totalBytes / (1024 * 1024 * 1024)) * 100) / 100,
      used_gb: Math.round((usedBytes / (1024 * 1024 * 1024)) * 100) / 100,
      free_gb: Math.round((freeBytes / (1024 * 1024 * 1024)) * 100) / 100,
      percent_used: Math.round((usedBytes / totalBytes) * 100 * 10) / 10,
      models_count: models.length,
      models: models,
    };
  } catch (error) {
    console.error(`Failed to get info for drive ${driveLetter}:`, error);
    return null;
  }
}

// Get all Windows drives info
async function getAllWindowsDrivesInfo(): Promise<DriveInfo[]> {
  const drives = await getWindowsDrives();
  const driveInfos: DriveInfo[] = [];
  
  for (const drive of drives) {
    const info = await getWindowsDriveInfo(drive);
    if (info) {
      driveInfos.push(info);
    }
  }
  
  // Sort by drive letter
  driveInfos.sort((a, b) => a.name.localeCompare(b.name));
  
  return driveInfos;
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
    const modelTypes = ['checkpoints', 'vae', 'clip', 'loras', 'unet', 'diffusion_models', 'text_encoders'];
    
    for (const modelType of modelTypes) {
      const typePath = path.join(modelsPath, modelType);
      try {
        const files = await fs.readdir(typePath);
        for (const file of files) {
          if (file.endsWith('.safetensors') || file.endsWith('.ckpt') || file.endsWith('.pth') || file.endsWith('.bin') || file.endsWith('.gguf')) {
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
  // Get real disk space on Windows - return all drives
  if (isWindows) {
    console.log('Windows detected, scanning all drives...');
    const drives = await getAllWindowsDrivesInfo();
    console.log(`Found ${drives.length} drives with total space`);
    
    // Calculate totals across ALL drives
    const totals = {
      total_gb: Math.round(drives.reduce((sum, d) => sum + d.total_gb, 0) * 100) / 100,
      used_gb: Math.round(drives.reduce((sum, d) => sum + d.used_gb, 0) * 100) / 100,
      free_gb: Math.round(drives.reduce((sum, d) => sum + d.free_gb, 0) * 100) / 100,
      models_count: drives.reduce((sum, d) => sum + d.models_count, 0),
      drives_count: drives.length,
      percent_used: drives.length > 0 
        ? Math.round((drives.reduce((sum, d) => sum + d.used_gb, 0) / drives.reduce((sum, d) => sum + d.total_gb, 0)) * 100 * 10) / 10
        : 0,
    };
    
    // Collect all models from all drives with their full paths
    const allModels = drives.flatMap(d => d.models);
    
    console.log(`Total disk space: ${totals.total_gb} GB across ${totals.drives_count} drives`);
    console.log(`Total models found: ${totals.models_count}`);
    
    return NextResponse.json({
      drives: drives,
      totals: totals,
      all_models: allModels, // All models with full paths including drive letters
      // For backwards compatibility, return first drive with models or first drive as main
      ...drives.find(d => d.models_count > 0) || drives[0] || {
        name: 'Unknown',
        display_name: 'Unknown Drive',
        mount_point: 'Unknown',
        total_gb: 0,
        used_gb: 0,
        free_gb: 0,
        percent_used: 0,
        models_count: 0,
        models: [],
      },
    });
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
      
      const driveInfo: DriveInfo = {
        name: device,
        display_name: 'AI Models Volume',
        mount_point: getModelsDisplayPath(),
        total_gb: Math.round(totalKb / (1024 * 1024) * 100) / 100,
        used_gb: Math.round(usedKb / (1024 * 1024) * 100) / 100,
        free_gb: Math.round(availKb / (1024 * 1024) * 100) / 100,
        percent_used: Math.round((usedKb / totalKb) * 100 * 10) / 10,
        models_count: allModels.length,
        models: allModels,
      };
      
      return NextResponse.json({
        drives: [driveInfo],
        totals: {
          total_gb: driveInfo.total_gb,
          used_gb: driveInfo.used_gb,
          free_gb: driveInfo.free_gb,
          models_count: driveInfo.models_count,
        },
        ...driveInfo,
      });
    }
    
    return NextResponse.json({ error: 'Failed to parse disk info' }, { status: 500 });
  } catch (error: any) {
    console.error('Disk space check failed:', error);
    return NextResponse.json({ error: 'Disk space check failed: ' + error.message }, { status: 500 });
  }
}
