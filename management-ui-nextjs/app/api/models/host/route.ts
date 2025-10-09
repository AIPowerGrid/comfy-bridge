import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';

export async function POST(request: Request) {
  try {
    const { model_id } = await request.json();
    
    if (!model_id) {
      return NextResponse.json(
        { error: 'Model ID is required' },
        { status: 400 }
      );
    }
    
    const envFilePath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    let envContent = await fs.readFile(envFilePath, 'utf-8');
    
    // Get current WORKFLOW_FILE value
    const match = envContent.match(/^WORKFLOW_FILE=(.*)$/m);
    let currentModels: string[] = [];
    
    if (match && match[1]) {
      currentModels = match[1].split(',').map(s => s.trim()).filter(Boolean);
    }
    
    // Add model if not already in the list
    if (!currentModels.includes(model_id)) {
      currentModels.push(model_id);
      
      const newModelsValue = currentModels.join(',');
      
      // Update WORKFLOW_FILE
      if (match) {
        envContent = envContent.replace(/^WORKFLOW_FILE=.*$/m, `WORKFLOW_FILE=${newModelsValue}`);
      } else {
        envContent += `\nWORKFLOW_FILE=${newModelsValue}`;
      }
      
      await fs.writeFile(envFilePath, envContent, 'utf-8');
      
      return NextResponse.json({
        success: true,
        message: `Model ${model_id} is now being hosted`,
        models: currentModels,
      });
    } else {
      return NextResponse.json({
        success: true,
        message: `Model ${model_id} is already being hosted`,
        models: currentModels,
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

