import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';

export async function GET() {
  try {
    const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
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
  } catch (error) {
    console.error('Error reading grid config:', error);
    return NextResponse.json({
      gridApiKey: '',
      workerName: '',
      aipgWallet: '',
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
    
    const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
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
    
    return NextResponse.json({
      success: true,
      message: 'Grid configuration saved successfully',
      fullWorkerName,
    });
  } catch (error: any) {
    console.error('Error saving grid config:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to save grid configuration' },
      { status: 500 }
    );
  }
}

