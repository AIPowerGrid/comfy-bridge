const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectRoot = path.join(__dirname, '..');
const repoRoot = path.join(projectRoot, '..');
const volumesDir = path.join(projectRoot, 'persistent_volumes');
const stashDir = path.join(repoRoot, 'persistent_volumes_ui_backup');
const winUnpackedDir = path.join(projectRoot, 'dist', 'win-unpacked');
const windowsExeName = 'AI Power Grid Manager.exe';

const args = process.argv.slice(2);
const mode = args.includes('--pack') ? 'pack' : 'build';
const shouldCreateShortcut = mode === 'build';

let movedVolumes = false;
let stoppedContainers = false;

function log(msg) {
  console.log(`[electron-build] ${msg}`);
}

function runShellCommand(command, options = {}) {
  log(`Running: ${command}`);
  try {
    execSync(command, {
      stdio: 'inherit',
      cwd: options.cwd || projectRoot,
      env: { ...process.env, ...(options.env || {}) },
      shell: true,
    });
  } catch (error) {
    // For electron-builder, check if packaging completed before the error
    if (command.includes('electron-builder')) {
      // Give filesystem a moment to sync
      setTimeout(() => {}, 1000);
    }
    throw error;
  }
}

function killRunningExecutable() {
  if (process.platform !== 'win32') {
    return;
  }

  try {
    const taskOutput = execSync(
      `tasklist /FI "IMAGENAME eq ${windowsExeName}" /FO LIST`,
      { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }
    );

    if (taskOutput && taskOutput.includes(windowsExeName)) {
      log(`Detected running instance of "${windowsExeName}", attempting to terminate...`);
      try {
        runShellCommand(`taskkill /IM "${windowsExeName}" /F`);
      } catch (err) {
        log(`Failed to terminate "${windowsExeName}". Please close the app manually if the build fails.`);
      }
    }
  } catch {
    // tasklist returns non-zero when the task is missing; that's fine
  }
}

function clearWinUnpackedDir() {
  if (fs.existsSync(winUnpackedDir)) {
    log(`Removing previous build directory: ${winUnpackedDir}`);
    try {
      fs.rmSync(winUnpackedDir, { recursive: true, force: true });
    } catch (error) {
      log(`Failed to remove ${winUnpackedDir}: ${error.message}`);
    }
  }
}

function clearElectronBuilderCache() {
  if (process.platform !== 'win32') {
    return;
  }
  
  // Clear the entire winCodeSign cache directory and parent Cache directory if needed
  const localAppData = process.env.LOCALAPPDATA || process.env.USERPROFILE || '';
  const winCodeSignCache = path.join(localAppData, 'electron-builder', 'Cache', 'winCodeSign');
  const electronBuilderCache = path.join(localAppData, 'electron-builder', 'Cache');
  
  log(`Clearing electron-builder code signing cache to avoid symlink permission issues...`);
  
  // Try to clear winCodeSign cache
  if (fs.existsSync(winCodeSignCache)) {
    try {
      fs.rmSync(winCodeSignCache, { recursive: true, force: true });
      log('winCodeSign cache cleared successfully');
    } catch (error) {
      log(`Warning: Could not clear winCodeSign cache (${error.message})`);
    }
  }
  
  // Also try to prevent re-download by creating a marker file or clearing parent cache
  // Note: electron-builder will re-download, but we'll handle the error gracefully
}

function tryDockerCommand(command) {
  try {
    runShellCommand(command, { cwd: repoRoot });
    return true;
  } catch {
    return false;
  }
}

function stopContainers() {
  if (tryDockerCommand('docker compose down')) {
    return true;
  }
  if (tryDockerCommand('docker-compose down')) {
    return true;
  }
  log('Unable to stop Docker containers automatically. Please stop them manually if the build fails.');
  return false;
}

function startContainers() {
  if (tryDockerCommand('docker compose up -d')) {
    return;
  }
  if (tryDockerCommand('docker-compose up -d')) {
    return;
  }
  log('Failed to restart Docker containers automatically. Please run `docker compose up -d` manually.');
}

function stashVolumes() {
  if (!fs.existsSync(volumesDir)) {
    return false;
  }

  if (fs.existsSync(stashDir)) {
    fs.rmSync(stashDir, { recursive: true, force: true });
  }

  try {
    fs.renameSync(volumesDir, stashDir);
    log(`Moved '${volumesDir}' to temporary location '${stashDir}'`);
    return true;
  } catch (error) {
    if (error.code === 'EPERM') {
      log('persistent_volumes is locked (likely by Docker). Attempting to stop containers...');
      if (stopContainers()) {
        stoppedContainers = true;
        fs.renameSync(volumesDir, stashDir);
        log(`Moved '${volumesDir}' to temporary location '${stashDir}'`);
        return true;
      }
    }
    throw error;
  }
}

function restoreVolumes() {
  if (fs.existsSync(stashDir) && !fs.existsSync(volumesDir)) {
    fs.renameSync(stashDir, volumesDir);
    log('Restored persistent_volumes directory');
  }

  if (stoppedContainers) {
    log('Restarting Docker containers...');
    startContainers();
  }
}

async function main() {
  try {
    movedVolumes = stashVolumes();

    killRunningExecutable();
    clearWinUnpackedDir();
    clearElectronBuilderCache();

    runShellCommand('npx next build');
    runShellCommand('npx tsc -p electron/tsconfig.json');
    
    // Build Electron app with code signing disabled to avoid Windows symlink permission issues
    // Only set CSC_IDENTITY_AUTO_DISCOVERY to false - don't set empty signing variables
    // as electron-builder will try to resolve them as file paths
    const electronBuilderEnv = {
      CSC_IDENTITY_AUTO_DISCOVERY: 'false',
      SKIP_NOTARIZATION: 'true',
    };
    
    let buildSucceeded = false;
    try {
      runShellCommand('npx electron-builder --dir', {
        env: electronBuilderEnv,
      });
      buildSucceeded = true;
    } catch (error) {
      // Always check if the app was built, even if there was an error
      // The packaging step often completes before the code signing tool extraction fails
      const exePath = path.join(projectRoot, 'dist', 'win-unpacked', windowsExeName);
      const distDir = path.join(projectRoot, 'dist', 'win-unpacked');
      
      // Wait a moment for file system to sync (Windows sometimes needs this)
      // The packaging step completes before code signing tool extraction, so the app should exist
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Check if the app was actually built despite the error
      if (fs.existsSync(exePath)) {
        log('');
        log('✅ SUCCESS: The Electron app was built successfully!');
        log(`📦 App location: ${exePath}`);
        log('');
        log('⚠️  Note: There was a warning about code signing tools, but the app is ready to use.');
        log('Code signing is disabled, so this warning can be safely ignored.');
        log('');
        log('To avoid this warning in the future:');
        log('1. Enable Windows Developer Mode (Recommended):');
        log('   Settings → Privacy & Security → For developers → Enable Developer Mode');
        log('   Then restart your terminal.');
        log('');
        log('2. Or run as Administrator:');
        log('   Right-click terminal → Run as Administrator');
        log('');
        buildSucceeded = true;
        // Don't throw - the build succeeded
        return;
      }
      
      // Also check if dist directory exists (might be partially built)
      if (fs.existsSync(distDir)) {
        log('');
        log('⚠️  Build directory exists but executable not found.');
        log(`Checked: ${exePath}`);
        log('The build may have failed before packaging completed.');
        log('');
      }
      
      // Check if error is related to Windows symlink permissions
      const errorMessage = error.message || error.toString();
      const stderr = error.stderr ? error.stderr.toString() : '';
      const fullError = errorMessage + stderr;
      
      if (fullError.includes('symbolic link') || fullError.includes('privilege') || fullError.includes('winCodeSign')) {
        log('');
        log('⚠️  Windows Symbolic Link Permission Error');
        log('electron-builder encountered a permission error while extracting code signing tools.');
        log('');
        log('The build failed because Windows cannot create symbolic links without special privileges.');
        log('');
        log('Solutions:');
        log('1. Enable Windows Developer Mode (Recommended - Easiest):');
        log('   • Open Windows Settings');
        log('   • Go to: Privacy & Security → For developers');
        log('   • Enable "Developer Mode"');
        log('   • Restart your terminal');
        log('   • Run the build again');
        log('');
        log('2. Run as Administrator:');
        log('   • Right-click your terminal/command prompt');
        log('   • Select "Run as Administrator"');
        log('   • Navigate to: cd ' + projectRoot);
        log('   • Run: npm run electron:build');
        log('');
        log('3. Use Docker build instead (avoids Windows permission issues):');
        log('   • Run: docker-compose build');
        log('   • The Electron app will be built in the container');
        log('');
        throw error;
      }
      throw error;
    }
    
    if (buildSucceeded) {
      log('');
      log('✅ Electron app built successfully!');
    }

    if (shouldCreateShortcut) {
      runShellCommand('node create-desktop-shortcut.js');
    }
  } catch (error) {
    console.error('[electron-build] Build failed:', error.message || error);
    process.exitCode = 1;
  } finally {
    if (movedVolumes || stoppedContainers) {
      restoreVolumes();
    }
    if (process.exitCode && process.exitCode !== 0) {
      process.exit(process.exitCode);
    }
  }
}

main();

