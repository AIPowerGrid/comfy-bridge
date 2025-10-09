import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';

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
    
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Error saving API keys:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
