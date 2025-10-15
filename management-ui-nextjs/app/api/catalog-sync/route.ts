import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

export async function POST() {
  try {
    console.log('Manual catalog sync requested');
    
    // Trigger catalog sync by calling the comfy-bridge container's sync endpoint
    const response = await fetch('http://comfy-bridge:8001/api/sync-catalog', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      throw new Error(`Sync request failed: ${response.status}`);
    }
    
    const result = await response.json();
    
    return NextResponse.json({ 
      success: true,
      message: 'Catalog sync completed successfully',
      output: result.output || '',
      error: result.error || null
    });
    
  } catch (error: any) {
    console.error('Catalog sync error:', error);
    
    return NextResponse.json({ 
      success: false,
      error: error.message || 'Unknown error',
      output: '',
      stderr: ''
    }, { status: 500 });
  }
}

export async function GET() {
  try {
    // Check sync status
    const syncLogPath = '/tmp/catalog_sync.log';
    const lastSyncPath = '/app/comfy-bridge/.last_catalog_sync';
    
    let lastSyncTime = null;
    let syncLog = '';
    
    try {
      const { promisify } = await import('util');
      const { exec } = await import('child_process');
      const execAsyncPromisified = promisify(exec);
      
      // Get last sync time
      try {
        const { stdout } = await execAsyncPromisified(`cat ${lastSyncPath}`, { timeout: 5000 });
        const timestamp = parseFloat(stdout.trim());
        lastSyncTime = new Date(timestamp * 1000).toISOString();
      } catch (e) {
        // File doesn't exist or can't be read
      }
      
      // Get recent sync log
      try {
        const { stdout } = await execAsyncPromisified(`tail -n 20 ${syncLogPath}`, { timeout: 5000 });
        syncLog = stdout;
      } catch (e) {
        // Log file doesn't exist or can't be read
      }
      
    } catch (e) {
      console.error('Error reading sync status:', e);
    }
    
    return NextResponse.json({
      last_sync_time: lastSyncTime,
      sync_log: syncLog,
      sync_service_running: true // Assume running if we can read the log
    });
    
  } catch (error: any) {
    console.error('Error getting sync status:', error);
    
    return NextResponse.json({ 
      error: error.message || 'Unknown error'
    }, { status: 500 });
  }
}

