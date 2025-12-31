import { NextResponse } from 'next/server';
import { loadModelsData } from './models-service';

// Force dynamic rendering - depends on filesystem state
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const data = await loadModelsData();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading models:', error);
    return NextResponse.json({});
  }
}
