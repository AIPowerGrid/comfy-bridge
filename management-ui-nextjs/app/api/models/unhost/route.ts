import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';

export const dynamic = 'force-dynamic';

const isWindows = process.platform === 'win32';

function getEnvPath() {
  if (isWindows) {
    return process.env.ENV_FILE_PATH || 'c:\\dev\\comfy-bridge\\.env';
  }
  return process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
}

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    
    if (!model_id) {
      return NextResponse.json({
        success: false,
        error: 'Model ID is required'
      }, { status: 400 });
    }
    
    console.log(`Stopping hosting for model: ${model_id}`);
    
    const envPath = getEnvPath();
    
    // Read current .env
    let envContent = '';
    try {
      envContent = await fs.readFile(envPath, 'utf-8');
    } catch (err) {
      return NextResponse.json({
        success: false,
        error: 'Could not read environment file'
      }, { status: 500 });
    }
    
    // Get current WORKFLOW_FILE value
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    
    if (!workflowMatch || !workflowMatch[1]) {
      return NextResponse.json({
        success: true,
        message: `Model ${model_id} was not being hosted`
      });
    }
    
    let currentWorkflows = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
    
    // Remove the model from the list (check multiple variations)
    const modelVariations = [
      model_id,
      `${model_id}.json`,
      model_id.toLowerCase(),
      `${model_id.toLowerCase()}.json`,
    ];
    
    const originalLength = currentWorkflows.length;
    currentWorkflows = currentWorkflows.filter(w => {
      const wLower = w.toLowerCase();
      const wNoJson = w.replace(/\.json$/, '').toLowerCase();
      return !modelVariations.some(v => v.toLowerCase() === wLower || v.toLowerCase() === wNoJson);
    });
    
    if (currentWorkflows.length === originalLength) {
      return NextResponse.json({
        success: true,
        message: `Model ${model_id} was not being hosted`
      });
    }
    
    // Update WORKFLOW_FILE in .env
    const newWorkflowValue = currentWorkflows.join(',');
    envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newWorkflowValue}`);
    
    await fs.writeFile(envPath, envContent, 'utf-8');
    
    console.log(`Updated WORKFLOW_FILE to: ${newWorkflowValue}`);
    
    // Trigger container restart
    try {
      const { exec } = await import('child_process');
      const { promisify } = await import('util');
      const execAsync = promisify(exec);
      
      if (isWindows) {
        await execAsync('docker-compose restart comfy-bridge', { 
          cwd: 'c:\\dev\\comfy-bridge' 
        });
      } else {
        await execAsync('docker-compose -f /app/comfy-bridge/docker-compose.yml restart comfy-bridge');
      }
      
      return NextResponse.json({
        success: true,
        restarted: true,
        message: `Stopped hosting ${model_id}. Container is restarting...`
      });
    } catch (restartError) {
      console.error('Failed to restart container:', restartError);
      return NextResponse.json({
        success: true,
        restarted: false,
        message: `Stopped hosting ${model_id}. Manual restart may be required.`,
        warning: 'Container restart failed'
      });
    }
    
  } catch (error: any) {
    console.error('Error unhosting model:', error);
    return NextResponse.json({
      success: false,
      error: error.message || 'Failed to stop hosting model'
    }, { status: 500 });
  }
}
