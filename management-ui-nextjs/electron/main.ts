import { app, BrowserWindow, Menu, shell, dialog } from 'electron';
import * as path from 'path';
import * as http from 'http';

let mainWindow: Electron.BrowserWindow | null;
const SERVER_URL = 'http://localhost:5000';

// Check if the Next.js server is running
function checkServerRunning(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(SERVER_URL, { timeout: 2000 }, (res) => {
      resolve(res.statusCode === 200 || res.statusCode === 404); // 404 is OK, means server is up
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

// Wait for server to be ready with retries
async function waitForServer(maxRetries = 30, delay = 1000): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    if (await checkServerRunning()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  return false;
}

function createWindow(): void {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    height: 800,
    width: 1200,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
    icon: path.join(__dirname, '../public/aipg.ico'),
    titleBarStyle: 'default',
    show: false, // Don't show until loaded
  });

  // Always connect to the Next.js server (assumes Docker containers are running)
  // The server should be running at http://localhost:5000
  loadApp();

  // Emitted when the window is closed.
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });
}

async function loadApp(): Promise<void> {
  if (!mainWindow) return;

  // Check if server is running
  const isRunning = await checkServerRunning();
  
  if (!isRunning) {
    // Wait a bit for server to start (in case it's just starting)
    const serverReady = await waitForServer(10, 500);
    
    if (!serverReady) {
      // Show error dialog
      const result = await dialog.showMessageBox(mainWindow!, {
        type: 'error',
        title: 'Connection Failed',
        message: 'Cannot connect to AI Power Grid Management UI',
        detail: `The Next.js server is not running at ${SERVER_URL}.\n\n` +
                `Please ensure Docker containers are running:\n` +
                `1. Open a terminal\n` +
                `2. Navigate to the comfy-bridge directory\n` +
                `3. Run: docker-compose up -d\n\n` +
                `Then restart this application.`,
        buttons: ['Retry', 'Open in Browser', 'Quit'],
        defaultId: 0,
      });

      // Handle MessageBoxReturnValue type (has response property)
      // TypeScript: showMessageBox returns MessageBoxReturnValue with response property
      let buttonIndex: number = 2; // Default to Quit
      const resultObj = result as { response?: number } | number | null;
      if (resultObj !== null && resultObj !== undefined) {
        if (typeof resultObj === 'object' && 'response' in resultObj && typeof resultObj.response === 'number') {
          buttonIndex = resultObj.response;
        } else if (typeof resultObj === 'number') {
          buttonIndex = resultObj;
        }
      }
      
      if (buttonIndex === 0) {
        // Retry
        setTimeout(() => loadApp(), 2000);
      } else if (buttonIndex === 1) {
        // Open in browser
        shell.openExternal(SERVER_URL);
        app.quit();
      } else {
        // Quit
        app.quit();
      }
      return;
    }
  }

  // Load the app from the server
  mainWindow.loadURL(SERVER_URL);
  
  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  // Handle navigation errors
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    if (errorCode === -105 || errorCode === -106) {
      // Connection refused or host not found
      dialog.showErrorBox(
        'Connection Error',
        `Failed to connect to ${SERVER_URL}.\n\n` +
        `Error: ${errorDescription}\n\n` +
        `Please ensure Docker containers are running.`
      );
    }
  });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(createWindow);

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  // On OS X it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Remove default menu
Menu.setApplicationMenu(null);
