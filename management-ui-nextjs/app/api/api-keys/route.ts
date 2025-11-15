import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Force dynamic rendering
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const envPath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    const content = await fs.readFile(envPath, 'utf-8');
    
    const keys = {
      huggingface: '',
      civitai: '',
    };
    
    const lines = content.split('\n');
    for (const line of lines) {
      if (line.startsWith('HUGGING_FACE_API_KEY=')) {
        keys.huggingface = line.split('=')[1]?.trim() || '';
      } else if (line.startsWith('CIVITAI_API_KEY=')) {
        keys.civitai = line.split('=')[1]?.trim() || '';
      }
    }
    
    return NextResponse.json(keys);
  } catch (error: any) {
    console.error('Error reading API keys:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { huggingface, civitai } = await request.json();
    const envPath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    
    // Read current .env file
    let content = await fs.readFile(envPath, 'utf-8');
    let lines = content.split('\n');
    
    // Update or add the API keys
    let hfFound = false;
    let civitaiFound = false;
    
    lines = lines.map(line => {
      if (line.startsWith('HUGGING_FACE_API_KEY=')) {
        hfFound = true;
        return `HUGGING_FACE_API_KEY=${huggingface}`;
      } else if (line.startsWith('CIVITAI_API_KEY=')) {
        civitaiFound = true;
        return `CIVITAI_API_KEY=${civitai}`;
      }
      return line;
    });
    
    // Add keys if they weren't found
    if (!hfFound) {
      lines.push(`HUGGING_FACE_API_KEY=${huggingface}`);
    }
    if (!civitaiFound) {
      lines.push(`CIVITAI_API_KEY=${civitai}`);
    }
    
    // Write back to file
    await fs.writeFile(envPath, lines.join('\n'), 'utf-8');
    
    // Restart containers to apply environment changes
    try {
      console.log('Restarting containers to apply API key changes...');
      
      // Restart containers using docker compose (newer syntax)
      const restartCommand = 'docker compose restart';
      const { stdout, stderr } = await execAsync(restartCommand);
      
      console.log('Container restart output:', stdout);
      if (stderr) {
        console.warn('Container restart warnings:', stderr);
      }
      
      return NextResponse.json({ 
        success: true,
        message: 'API keys saved and containers restarted successfully',
        restartOutput: stdout,
      });
    } catch (restartError: any) {
      console.error('Failed to restart containers:', restartError);
      
      // Still return success for the API key save, but warn about restart failure
      return NextResponse.json({
        success: true,
        message: 'API keys saved, but container restart failed. Please restart manually.',
        restartError: restartError.message,
        warning: 'Please restart containers manually to apply changes',
      });
    }
  } catch (error: any) {
    console.error('Error saving API keys:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
