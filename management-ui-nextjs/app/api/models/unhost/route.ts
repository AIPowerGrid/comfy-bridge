import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    
    if (!model_id) {
      return NextResponse.json(
        { error: 'Model ID is required' },
        { status: 400 }
      );
    }
    
    // Strip .json extension if present in model_id
    const modelIdWithoutJson = model_id.endsWith('.json') ? model_id.slice(0, -5) : model_id;
    
    const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    let envContent = await fs.readFile(envFilePath, 'utf-8');
    
    // Get current WORKFLOW_FILE value and strip .json from each model
    const match = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    let currentModels: string[] = [];
    
    if (match && match[1]) {
      currentModels = match[1].split(',').map(s => {
        const trimmed = s.trim();
        return trimmed.endsWith('.json') ? trimmed.slice(0, -5) : trimmed;
      }).filter(Boolean);
    }
    
    // Remove model from the list
    const initialLength = currentModels.length;
    currentModels = currentModels.filter(m => m !== modelIdWithoutJson);
    
    if (currentModels.length < initialLength) {
      const newModelsValue = currentModels.join(',');
      
      // Update WORKFLOW_FILE
      if (match) {
        envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newModelsValue}`);
      }
      
      await fs.writeFile(envFilePath, envContent, 'utf-8');
      
      // Restart containers to apply changes
      console.log('Restarting containers to stop hosting model...');
      try {
        const scriptPath = process.env.COMFY_BRIDGE_PATH || '/app/comfy-bridge';
        await execAsync('docker-compose restart', {
          cwd: scriptPath,
          timeout: 60000,
        });
        
        return NextResponse.json({
          success: true,
          message: `Model ${modelIdWithoutJson} is no longer being hosted. Containers restarted.`,
          models: currentModels,
          restarted: true,
        });
      } catch (restartError: any) {
        console.error('Container restart failed:', restartError);
        return NextResponse.json({
          success: true,
          message: `Model ${modelIdWithoutJson} removed from hosting, but failed to restart containers. Please restart manually.`,
          models: currentModels,
          restarted: false,
          warning: restartError.message,
        });
      }
    } else {
      return NextResponse.json({
        success: true,
        message: `Model ${modelIdWithoutJson} was not being hosted`,
        models: currentModels,
        restarted: false,
      });
    }
  } catch (error: any) {
    console.error('Error unhosting model:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to unhost model' },
      { status: 500 }
    );
  }
}

