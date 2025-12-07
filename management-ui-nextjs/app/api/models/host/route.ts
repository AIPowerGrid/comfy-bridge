import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';

export const dynamic = 'force-dynamic';

const isWindows = process.platform === 'win32';

function getEnvPath() {
  if (isWindows) {
    return process.env.ENV_FILE_PATH || 'c:\\dev\\comfy-bridge\\.env';
  }
  return process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
}

function getWorkflowsPath() {
  if (isWindows) {
    return 'c:\\dev\\comfy-bridge\\workflows';
  }
  return '/app/comfy-bridge/workflows';
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
    
    console.log(`Starting to host model: ${model_id}`);
    
    const envPath = getEnvPath();
    const workflowsPath = getWorkflowsPath();
    
    // Read current .env
    let envContent = '';
    try {
      envContent = await fs.readFile(envPath, 'utf-8');
    } catch (err) {
      // File might not exist yet
      envContent = '';
    }
    
    // Check if workflow file exists for this model
    const workflowFile = `${model_id}.json`;
    const workflowFullPath = path.join(workflowsPath, workflowFile);
    
    let workflowExists = false;
    try {
      await fs.access(workflowFullPath);
      workflowExists = true;
    } catch (err) {
      console.log(`Workflow file not found: ${workflowFullPath}`);
    }
    
    if (!workflowExists) {
      // Try with lowercase
      const lowerWorkflowFile = `${model_id.toLowerCase()}.json`;
      const lowerWorkflowPath = path.join(workflowsPath, lowerWorkflowFile);
      try {
        await fs.access(lowerWorkflowPath);
        workflowExists = true;
      } catch (err) {
        // Also try with common naming patterns
        const patterns = [
          `${model_id.replace(/[^a-zA-Z0-9]/g, '_')}.json`,
          `${model_id.replace(/[^a-zA-Z0-9]/g, '-')}.json`,
          `${model_id.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`,
        ];
        
        for (const pattern of patterns) {
          try {
            await fs.access(path.join(workflowsPath, pattern));
            workflowExists = true;
            break;
          } catch (err) {
            // Continue checking
          }
        }
      }
    }
    
    if (!workflowExists) {
      return NextResponse.json({
        success: false,
        error: `No workflow file found for ${model_id}. Please ensure a workflow file exists in the workflows directory.`
      }, { status: 400 });
    }
    
    // Get current WORKFLOW_FILE value
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    let currentWorkflows: string[] = [];
    
    if (workflowMatch && workflowMatch[1]) {
      currentWorkflows = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
    }
    
    // Add the new model if not already present
    const modelWorkflow = `${model_id}.json`;
    if (!currentWorkflows.includes(modelWorkflow) && !currentWorkflows.includes(model_id)) {
      currentWorkflows.push(modelWorkflow);
    }
    
    // Update WORKFLOW_FILE in .env
    const newWorkflowValue = currentWorkflows.join(',');
    
    if (workflowMatch) {
      envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newWorkflowValue}`);
    } else {
      envContent += `\nWORKFLOW_FILE=${newWorkflowValue}\n`;
    }
    
    await fs.writeFile(envPath, envContent, 'utf-8');
    
    console.log(`Updated WORKFLOW_FILE to: ${newWorkflowValue}`);
    
    // Trigger container restart
    try {
      const { exec } = await import('child_process');
      const { promisify } = await import('util');
      const execAsync = promisify(exec);
      
      if (isWindows) {
        // On Windows, use docker-compose from the comfy-bridge directory
        await execAsync('docker-compose restart comfy-bridge', { 
          cwd: 'c:\\dev\\comfy-bridge' 
        });
      } else {
        // In Docker, use docker-compose
        await execAsync('docker-compose -f /app/comfy-bridge/docker-compose.yml restart comfy-bridge');
      }
    } catch (restartError) {
      console.error('Failed to restart container:', restartError);
      // Don't fail the request, just note the warning
      return NextResponse.json({
        success: true,
        requires_restart: true,
        message: `Model ${model_id} configured for hosting. Manual restart may be required.`,
        warning: 'Container restart failed - please restart manually'
      });
    }
    
    return NextResponse.json({
      success: true,
      requires_restart: true,
      message: `Now hosting ${model_id}. Container is restarting...`
    });
    
  } catch (error: any) {
    console.error('Error hosting model:', error);
    return NextResponse.json({
      success: false,
      error: error.message || 'Failed to host model'
    }, { status: 500 });
  }
}
