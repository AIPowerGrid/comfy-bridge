import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const dynamic = 'force-dynamic';

export async function POST() {
  try {
    console.log('Manual catalog sync requested');
    
    // Run the catalog sync script
    const { stdout, stderr } = await execAsync('python3 /app/comfy-bridge/catalog_sync.py', {
      timeout: 60000, // 1 minute timeout
      cwd: '/app/comfy-bridge'
    });
    
    console.log('Catalog sync output:', stdout);
    if (stderr) {
      console.log('Catalog sync stderr:', stderr);
    }
    
    return NextResponse.json({ 
      success: true,
      message: 'Catalog sync completed successfully',
      output: stdout,
      error: stderr || null
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
      const { execAsync } = await import('util');
      const { exec } = await import('child_process');
      const execAsyncPromisified = execAsync;
      
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
