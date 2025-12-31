import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';
import { checkWorkflowModels, type WorkflowCheckResult } from '@/lib/workflowModelChecker';

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
    // Try multiple naming variations to find a match
    const namingVariations = [
      `${model_id}.json`,
      `${model_id.toLowerCase()}.json`,
      `${model_id.replace(/[^a-zA-Z0-9.-]/g, '_')}.json`,
      `${model_id.replace(/[^a-zA-Z0-9.-]/g, '-')}.json`,
      `${model_id.toLowerCase().replace(/[^a-z0-9.-]/g, '_')}.json`,
      `${model_id.toLowerCase().replace(/[^a-z0-9.-]/g, '-')}.json`,
      // Handle cases like "flux.1-krea-dev" -> "flux1_krea_dev.json"
      `${model_id.replace(/\./g, '').replace(/-/g, '_')}.json`,
    ];
    
    let foundWorkflowFile = '';
    
    // First try the exact variations
    for (const variant of namingVariations) {
      try {
        await fs.access(path.join(workflowsPath, variant));
        foundWorkflowFile = variant;
        console.log(`Found workflow file: ${variant}`);
        break;
      } catch (err) {
        // Continue checking
      }
    }
    
    // If not found, list all workflows and try fuzzy matching
    if (!foundWorkflowFile) {
      try {
        const files = await fs.readdir(workflowsPath);
        const modelLower = model_id.toLowerCase().replace(/[^a-z0-9]/g, '');
        
        for (const file of files) {
          if (!file.endsWith('.json')) continue;
          const fileLower = file.toLowerCase().replace(/[^a-z0-9]/g, '');
          // Check if model name is contained in filename or vice versa
          if (fileLower.includes(modelLower) || modelLower.includes(fileLower.replace('json', ''))) {
            foundWorkflowFile = file;
            console.log(`Found workflow file via fuzzy match: ${file} for model ${model_id}`);
            break;
          }
        }
      } catch (err) {
        console.error('Error listing workflows directory:', err);
      }
    }
    
    if (!foundWorkflowFile) {
      console.log(`No workflow file found for ${model_id}. Checked: ${namingVariations.join(', ')}`);
      return NextResponse.json({
        success: false,
        error: `No workflow file found for ${model_id}. Please ensure a workflow file exists in the workflows directory.`
      }, { status: 400 });
    }
    
    // Check if required models are installed
    const workflowFullPath = path.join(workflowsPath, foundWorkflowFile);
    let modelCheckResult: WorkflowCheckResult | null = null;
    
    try {
      modelCheckResult = await checkWorkflowModels(workflowFullPath);
      console.log(`Model check for ${model_id}:`, JSON.stringify(modelCheckResult, null, 2));
      
      if (!modelCheckResult.allModelsInstalled) {
        const missingList = modelCheckResult.missingModels
          .map(m => `${m.filename} (${m.loaderType})`)
          .join(', ');
        
        console.log(`Missing models for ${model_id}: ${missingList}`);
        
        return NextResponse.json({
          success: false,
          error: `Cannot host ${model_id}: missing required model files`,
          missing_models: modelCheckResult.missingModels.map(m => ({
            filename: m.filename,
            loader: m.loaderType
          })),
          message: `The following model files are required but not installed: ${missingList}`
        }, { status: 400 });
      }
      
      console.log(`All required models installed for ${model_id}`);
    } catch (checkError: any) {
      console.warn(`Could not verify models for ${model_id}:`, checkError.message);
      // Continue anyway if we can't check - runtime will catch issues
    }
    
    // Get current WORKFLOW_FILE value
    const workflowMatch = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    let currentWorkflows: string[] = [];
    
    if (workflowMatch && workflowMatch[1]) {
      currentWorkflows = workflowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
    }
    
    // Add the found workflow file if not already present
    // Check both the found filename and model_id variations
    const alreadyPresent = currentWorkflows.some(w => {
      const wLower = w.toLowerCase().replace(/\.json$/, '');
      const foundLower = foundWorkflowFile.toLowerCase().replace(/\.json$/, '');
      const modelLower = model_id.toLowerCase();
      return wLower === foundLower || wLower === modelLower || w === foundWorkflowFile;
    });
    
    if (!alreadyPresent) {
      currentWorkflows.push(foundWorkflowFile);
      console.log(`Adding ${foundWorkflowFile} to WORKFLOW_FILE`);
    } else {
      console.log(`Workflow ${foundWorkflowFile} already in WORKFLOW_FILE`);
    }
    
    // If already present, no need to update file
    if (alreadyPresent) {
      return NextResponse.json({
        success: true,
        requires_restart: false,
        already_hosted: true,
        message: `Model ${model_id} is already configured for hosting.`
      });
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
    
    // Return success - the UI will handle the restart via countdown
    return NextResponse.json({
      success: true,
      requires_restart: true,
      message: `Model ${model_id} configured for hosting. Container restart required.`
    });
    
  } catch (error: any) {
    console.error('Error hosting model:', error);
    return NextResponse.json({
      success: false,
      error: error.message || 'Failed to host model'
    }, { status: 500 });
  }
}
