const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectRoot = path.join(__dirname, '..');
const repoRoot = path.join(projectRoot, '..');
const volumesDir = path.join(projectRoot, 'persistent_volumes');
const stashDir = path.join(repoRoot, 'persistent_volumes_ui_backup');

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
  execSync(command, {
    stdio: 'inherit',
    cwd: options.cwd || projectRoot,
    env: { ...process.env, ...(options.env || {}) },
    shell: true,
  });
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

    runShellCommand('npx next build');
    runShellCommand('npx tsc -p electron/tsconfig.json');
    runShellCommand('npx electron-builder --dir', {
      CSC_IDENTITY_AUTO_DISCOVERY: 'false',
    });

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

