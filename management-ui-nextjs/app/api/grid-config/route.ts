import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import { restartDockerContainers } from '@/lib/docker';

// Check if running in Docker or locally
const isWindows = process.platform === 'win32';
const isLocalDev = isWindows || !process.env.DOCKER_CONTAINER;

// Get the correct .env path based on platform
function getEnvPath() {
  if (isWindows) {
    return process.env.ENV_FILE_PATH || 'c:\\dev\\comfy-bridge\\.env';
  }
  return process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
}

export async function GET() {
  try {
    const envFilePath = getEnvPath();
    const envContent = await fs.readFile(envFilePath, 'utf-8');
    
    // Parse GRID_API_KEY
    const gridApiKeyMatch = envContent.match(/^GRID_API_KEY=(.*)$/m);
    const gridApiKey = gridApiKeyMatch ? gridApiKeyMatch[1].trim() : '';
    
    // Parse GRID_WORKER_NAME and split it
    const workerNameMatch = envContent.match(/^GRID_WORKER_NAME=(.*)$/m);
    let workerName = '';
    let aipgWallet = '';
    
    if (workerNameMatch && workerNameMatch[1]) {
      const fullWorkerName = workerNameMatch[1].trim();
      const parts = fullWorkerName.split('.');
      if (parts.length >= 2) {
        workerName = parts[0];
        aipgWallet = parts.slice(1).join('.');
      }
    }
    
    return NextResponse.json({
      gridApiKey,
      workerName,
      aipgWallet,
    });
  } catch (error: any) {
    console.error('Error reading grid config:', error);
    return NextResponse.json({
      gridApiKey: '',
      workerName: '',
      aipgWallet: '',
      error: 'Could not read .env file: ' + error.message,
    });
  }
}

export async function POST(request: Request) {
  try {
    const { gridApiKey, workerName, aipgWallet } = await request.json();
    
    // Validate inputs
    if (!gridApiKey || !workerName || !aipgWallet) {
      return NextResponse.json(
        { error: 'All fields are required' },
        { status: 400 }
      );
    }
    
    // Construct full worker name
    const fullWorkerName = `${workerName}.${aipgWallet}`;
    
    const envFilePath = getEnvPath();
    let envContent = await fs.readFile(envFilePath, 'utf-8');
    
    // Update GRID_API_KEY
    if (envContent.match(/^GRID_API_KEY=/m)) {
      envContent = envContent.replace(/^GRID_API_KEY=.*$/m, `GRID_API_KEY=${gridApiKey}`);
    } else {
      envContent += `\nGRID_API_KEY=${gridApiKey}`;
    }
    
    // Update GRID_WORKER_NAME
    if (envContent.match(/^GRID_WORKER_NAME=/m)) {
      envContent = envContent.replace(/^GRID_WORKER_NAME=.*$/m, `GRID_WORKER_NAME=${fullWorkerName}`);
    } else {
      envContent += `\nGRID_WORKER_NAME=${fullWorkerName}`;
    }
    
    await fs.writeFile(envFilePath, envContent, 'utf-8');
    
    // Skip Docker restart on Windows (local dev mode)
    if (isWindows) {
      return NextResponse.json({
        success: true,
        message: 'Grid configuration saved successfully',
        fullWorkerName,
      });
    }
    
    // Restart containers to apply environment changes (Docker only)
    try {
      console.log('Restarting containers to apply environment changes...');
      
      const { stdout, stderr, command, composeDir } = await restartDockerContainers();
      
      console.log(`Container restart output (${command} @ ${composeDir}):`, stdout);
      if (stderr) {
        console.warn('Container restart warnings:', stderr);
      }
      
      return NextResponse.json({
        success: true,
        message: 'Grid configuration saved and containers restarted successfully',
        fullWorkerName,
        restartOutput: stdout,
        restartCommand: command,
      });
    } catch (restartError: any) {
      console.error('Failed to restart containers:', restartError);
      
      return NextResponse.json({
        success: true,
        message: 'Grid configuration saved, but container restart failed. Please restart manually.',
        fullWorkerName,
        restartError: restartError?.stderr || restartError?.message,
        warning: 'Please restart containers manually to apply changes',
      });
    }
  } catch (error: any) {
    console.error('Error saving grid config:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to save grid configuration' },
      { status: 500 }
    );
  }
}

