const { execSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

const platform = process.platform;
const distDir = path.join(__dirname, 'dist');
const desktopPath = path.join(os.homedir(), 'Desktop');

function createShortcut() {
  let exePath = '';
  let shortcutPath = '';
  let iconPath = path.join(__dirname, 'public', 'aipg.ico');
  if (!fs.existsSync(iconPath)) {
    iconPath = path.join(__dirname, 'public', 'logo.png');
  }

  if (platform === 'win32') {
    // Windows
    exePath = path.join(distDir, 'win-unpacked', 'AI Power Grid Manager.exe');
    
    if (!fs.existsSync(exePath)) {
      console.log('Executable not found, skipping shortcut creation');
      return;
    }

    // Get Desktop path using PowerShell (more reliable than os.homedir())
    let actualDesktopPath = desktopPath;
    try {
      const desktopPathCmd = 'powershell -Command "[Environment]::GetFolderPath(\'Desktop\')"';
      actualDesktopPath = execSync(desktopPathCmd, { encoding: 'utf8' }).trim();
    } catch (error) {
      console.warn('Could not get Desktop path via PowerShell, using default');
    }

    // Ensure Desktop directory exists
    if (!fs.existsSync(actualDesktopPath)) {
      console.log(`Desktop directory not found: ${actualDesktopPath}, skipping shortcut creation`);
      return;
    }

    shortcutPath = path.join(actualDesktopPath, 'AI Power Grid Manager.lnk');

    try {
      let iconFullPath = '';
      if (fs.existsSync(iconPath)) {
        try {
          const iconDest = path.join(distDir, 'win-unpacked', 'AI-Power-Grid-Manager.ico');
          fs.mkdirSync(path.dirname(iconDest), { recursive: true });
          fs.copyFileSync(iconPath, iconDest);
          iconFullPath = path.resolve(iconDest);
        } catch (err) {
          console.warn('Could not copy icon for shortcut:', err);
          iconFullPath = path.resolve(iconPath);
        }
      }

      // Use Windows-style paths for PowerShell
      const exeFullPath = path.resolve(exePath);
      const workDir = path.dirname(exePath);
      const iconArg = iconFullPath ? `${iconFullPath},0` : '';

      let psScript = `$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('${shortcutPath.replace(/\\/g, '/')}'); $Shortcut.TargetPath = '${exeFullPath.replace(/\\/g, '/')}'; $Shortcut.WorkingDirectory = '${workDir.replace(/\\/g, '/')}'; $Shortcut.Description = 'AI Power Grid Worker Management UI'`;
      
      if (iconArg) {
        psScript += `; $Shortcut.IconLocation = '${iconArg.replace(/\\/g, '/')}'`;
      }
      
      psScript += '; $Shortcut.Save()';
      
      execSync(`powershell -Command "${psScript.replace(/"/g, '\\"')}"`, { stdio: 'inherit' });
      console.log(`✓ Desktop shortcut created: ${shortcutPath}`);
    } catch (error) {
      console.error('Failed to create desktop shortcut:', error.message);
      console.error('You can manually create a shortcut to:', path.resolve(exePath));
    }
  } else if (platform === 'darwin') {
    // macOS
    const appPath = path.join(distDir, 'mac', 'AI Power Grid Manager.app');
    if (!fs.existsSync(appPath)) {
      // Try unpacked location
      const unpackedAppPath = path.join(distDir, 'mac-unpacked', 'AI Power Grid Manager.app');
      if (fs.existsSync(unpackedAppPath)) {
        exePath = unpackedAppPath;
      } else {
        console.log('App bundle not found, skipping shortcut creation');
        return;
      }
    } else {
      exePath = appPath;
    }

    shortcutPath = path.join(desktopPath, 'AI Power Grid Manager');
    
    try {
      const fullPath = path.resolve(exePath);
      execSync(`osascript -e "tell application \\"Finder\\" to make alias file at POSIX file \\"${desktopPath}\\" to POSIX file \\"${fullPath}\\""`, { stdio: 'inherit' });
      console.log(`✓ Desktop shortcut created: ${shortcutPath}`);
    } catch (error) {
      console.error('Failed to create desktop shortcut:', error.message);
    }
  } else if (platform === 'linux') {
    // Linux
    let exeFile = '';
    if (fs.existsSync(path.join(distDir, 'AI Power Grid Manager.AppImage'))) {
      exeFile = path.join(distDir, 'AI Power Grid Manager.AppImage');
    } else if (fs.existsSync(path.join(distDir, 'linux-unpacked', 'AI Power Grid Manager'))) {
      exeFile = path.join(distDir, 'linux-unpacked', 'AI Power Grid Manager');
    } else if (fs.existsSync(path.join(distDir, 'linux-unpacked', 'aipg-model-manager'))) {
      exeFile = path.join(distDir, 'linux-unpacked', 'aipg-model-manager');
    }
    
    if (!exeFile || !fs.existsSync(exeFile)) {
      console.log('Executable not found, skipping shortcut creation');
      return;
    }

    shortcutPath = path.join(desktopPath, 'AI Power Grid Manager.desktop');
    const fullPath = path.resolve(exeFile);
    const iconFullPath = path.resolve(iconPath);
    
    const desktopEntry = `[Desktop Entry]
Version=1.0
Type=Application
Name=AI Power Grid Manager
Comment=AI Power Grid Worker Management UI
Exec="${fullPath}"
Icon=${iconFullPath}
Terminal=false
Categories=Utility;
`;
    
    try {
      fs.writeFileSync(shortcutPath, desktopEntry);
      fs.chmodSync(shortcutPath, '755');
      console.log(`✓ Desktop shortcut created: ${shortcutPath}`);
    } catch (error) {
      console.error('Failed to create desktop shortcut:', error.message);
    }
  }
}

createShortcut();

