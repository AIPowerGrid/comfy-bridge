import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import * as path from 'path';
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
    
    // Verify model is installed before allowing hosting
    const modelConfigPath = '/app/comfy-bridge/model_configs.json';
    const modelsPath = process.env.MODELS_PATH || '/app/ComfyUI/models';
    
    try {
      const configData = await fs.readFile(modelConfigPath, 'utf-8');
      const modelConfigs = JSON.parse(configData);
      const modelInfo = modelConfigs[modelIdWithoutJson];
      
      if (!modelInfo) {
        return NextResponse.json({
          success: false,
          error: 'Model not found in catalog'
        }, { status: 404 });
      }
      
      // Check if model files are installed
      const files = modelInfo.files || (modelInfo.filename ? [{ path: modelInfo.filename, file_type: modelInfo.type || 'checkpoints' }] : []);
      
      if (files.length === 0) {
        return NextResponse.json({
          success: false,
          error: 'Model has no files defined in catalog'
        }, { status: 400 });
      }
      
      // Check if all files exist
      for (const file of files) {
        const fileName = file.path;
        const fileType = file.file_type || 'checkpoints';
        const filePath = path.join(modelsPath, fileType, fileName);
        
        try {
          await fs.access(filePath);
        } catch (err) {
          return NextResponse.json({
            success: false,
            error: `Model not installed. Missing file: ${fileName}`,
            missing_file: fileName,
            file_path: `${fileType}/${fileName}`
          }, { status: 400 });
        }
      }
      
      console.log(`Verified ${files.length} file(s) installed for ${modelIdWithoutJson}`);
    } catch (error) {
      console.error('Error verifying model installation:', error);
      return NextResponse.json({
        success: false,
        error: 'Failed to verify model installation'
      }, { status: 500 });
    }
    
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
    
    // Check if this is a new model being enabled
    const isNewModel = !currentModels.includes(modelIdWithoutJson);
    
    // Check if workflow file exists, create template if not
    const workflowsPath = process.env.COMFY_BRIDGE_PATH 
      ? path.join(process.env.COMFY_BRIDGE_PATH, 'workflows')
      : '/app/comfy-bridge/workflows';
    
    const workflowFilePath = path.join(workflowsPath, `${modelIdWithoutJson}.json`);
    
    try {
      await fs.access(workflowFilePath);
    } catch (error) {
      // Workflow file doesn't exist, create a template
      console.log(`Creating template workflow file for ${modelIdWithoutJson}`);
      
      // Create a basic workflow template
      const templateWorkflow = {
        "3": {
          "inputs": {
            "seed": 1,
            "steps": 20,
            "cfg": 7,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0]
          },
          "class_type": "KSampler",
          "_meta": { "title": "KSampler" }
        },
        "4": {
          "inputs": {
            "ckpt_name": "checkpoint_name.safetensors"
          },
          "class_type": "CheckpointLoaderSimple",
          "_meta": { "title": "Load Checkpoint" }
        },
        "5": {
          "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1
          },
          "class_type": "EmptyLatentImage",
          "_meta": { "title": "Empty Latent Image" }
        },
        "6": {
          "inputs": {
            "text": "prompt",
            "clip": ["4", 1]
          },
          "class_type": "CLIPTextEncode",
          "_meta": { "title": "CLIP Text Encode (Prompt)" }
        },
        "7": {
          "inputs": {
            "text": "negative prompt",
            "clip": ["4", 1]
          },
          "class_type": "CLIPTextEncode",
          "_meta": { "title": "CLIP Text Encode (Negative)" }
        },
        "8": {
          "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2]
          },
          "class_type": "VAEDecode",
          "_meta": { "title": "VAE Decode" }
        },
        "9": {
          "inputs": {
            "filename_prefix": "ComfyUI",
            "images": ["8", 0]
          },
          "class_type": "SaveImage",
          "_meta": { "title": "Save Image" }
        }
      };
      
      // Ensure workflows directory exists
      await fs.mkdir(workflowsPath, { recursive: true });
      
      // Write the template workflow
      await fs.writeFile(workflowFilePath, JSON.stringify(templateWorkflow, null, 2), 'utf-8');
      
      console.log(`Created template workflow file: ${workflowFilePath}`);
    }
    
    // Add model if not already in the list (without .json extension)
    if (isNewModel) {
      currentModels.push(modelIdWithoutJson);
      
      const newModelsValue = currentModels.join(',');
      
      // Update WORKFLOW_FILE
      if (match) {
        envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newModelsValue}`);
      } else {
        envContent += `\nWORKFLOW_FILE=${newModelsValue}`;
      }
      
      await fs.writeFile(envFilePath, envContent, 'utf-8');
      
      // Return success, frontend will handle restart/rebuild
      return NextResponse.json({
        success: true,
        message: `Model ${modelIdWithoutJson} is now being hosted. Containers will restart to apply changes.`,
        models: currentModels,
        requires_restart: true, // Tell frontend to trigger rebuild
      });
    } else {
      return NextResponse.json({
        success: true,
        message: `Model ${modelIdWithoutJson} is already being hosted`,
        models: currentModels,
        restarted: false,
      });
    }
  } catch (error: any) {
    console.error('Error hosting model:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to host model' },
      { status: 500 }
    );
  }
}

