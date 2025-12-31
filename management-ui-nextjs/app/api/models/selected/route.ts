import { NextResponse } from 'next/server';
import * as fs from 'fs/promises';

// Force dynamic rendering - depends on filesystem state
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const envPath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    const content = await fs.readFile(envPath, 'utf-8');
    
    for (const line of content.split('\n')) {
      if (line.startsWith('GRID_MODEL=')) {
        const value = line.split('=')[1].split('#')[0].trim();
        if (value) {
          return NextResponse.json({ models: value.split(',').map(m => m.trim()) });
        }
      }
    }
    
    return NextResponse.json({ models: [] });
  } catch (error) {
    console.error('Error reading selected models:', error);
    return NextResponse.json({ error: 'Failed to read selected models' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { models } = await request.json();
    const envPath = process.env.ENV_FILE_PATH || '/app/comfy-bridge/.env';
    
    // Read current .env
    const content = await fs.readFile(envPath, 'utf-8');
    const lines = content.split('\n');
    
    // Remove ALL existing GRID_MODEL lines
    const newLines: string[] = [];
    let preservedComment = '';
    let gridModelFound = false;
    
    for (const line of lines) {
      if (line.startsWith('GRID_MODEL=')) {
        if (!gridModelFound && line.includes('#')) {
          preservedComment = '  #' + line.split('#')[1];
        }
        gridModelFound = true;
        continue; // Skip this line
      }
      newLines.push(line);
    }
    
    // Find insertion point (after GRID_MAX_PIXELS)
    let insertIndex = -1;
    for (let i = 0; i < newLines.length; i++) {
      if (newLines[i].startsWith('GRID_MAX_PIXELS=')) {
        insertIndex = i + 1;
        break;
      }
    }
    
    // Create new GRID_MODEL line
    const modelValue = models.join(',');
    const newModelLine = preservedComment 
      ? `GRID_MODEL=${modelValue}${preservedComment}`
      : `GRID_MODEL=${modelValue}`;
    
    // Insert at appropriate position
    if (insertIndex > 0) {
      newLines.splice(insertIndex, 0, newModelLine);
    } else {
      newLines.push(newModelLine);
    }
    
    // Write back
    await fs.writeFile(envPath, newLines.join('\n'));
    
    return NextResponse.json({ success: true, message: 'Models updated successfully' });
  } catch (error) {
    console.error('Error updating models:', error);
    return NextResponse.json({ error: 'Failed to update models' }, { status: 500 });
  }
}

