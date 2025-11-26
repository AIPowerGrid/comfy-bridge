@echo off
setlocal enabledelayedexpansion

REM Check for admin privileges
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo.
echo ========================================
echo  AI Power Grid Worker - Starting...
echo ========================================
echo.

REM Check disk space (50GB minimum)
echo [1/5] Checking disk space...
for /f "delims=" %%a in ('powershell -Command "$drive = (Get-Location).Drive.Root; $free = (Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Root -eq $drive}).Free; [math]::Round($free / 1GB, 0)"') do set FREE_SPACE_GB=%%a

if "%FREE_SPACE_GB%"=="" (
    echo    Warning: Could not check disk space, continuing...
) else if %FREE_SPACE_GB% LSS 50 (
    echo.
    echo ERROR: Insufficient disk space
    echo Required: 50 GB minimum
    echo Available: %FREE_SPACE_GB% GB
    echo.
    echo Free up disk space and try again.
    pause
    exit /b 1
) else (
    echo    Disk space OK (%FREE_SPACE_GB% GB available)
)

REM Check Docker installation
echo [2/5] Checking Docker installation...
where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker is not installed
    echo.
    echo Install Docker Desktop: https://www.docker.com/products/docker-desktop
    echo Or run: winget install Docker.DockerDesktop
    echo.
    echo After installation, start Docker Desktop and run this script again.
    echo.
    set /p INSTALL_DOCKER="Open Docker download page? (Y/N): "
    if /i "!INSTALL_DOCKER!"=="Y" start https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo    Docker found

REM Check Docker is running
echo [3/5] Checking Docker is running...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker is not running
    echo.
    echo Start Docker Desktop and wait for it to fully start.
    echo.
    set /p START_DOCKER="Start Docker Desktop now? (Y/N): "
    if /i "!START_DOCKER!"=="Y" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
        if errorlevel 1 (
            echo    Docker Desktop not found in default location.
            echo    Please start it manually.
            pause
            exit /b 1
        )
        echo    Waiting for Docker to start...
        timeout /t 10 /nobreak >nul
        :WAIT_DOCKER
        docker info >nul 2>&1
        if errorlevel 1 (
            timeout /t 5 /nobreak >nul
            goto WAIT_DOCKER
        )
        echo    Docker is running
    ) else (
        pause
        exit /b 1
    )
) else (
    echo    Docker is running
)

REM Check .env file
echo [4/5] Checking configuration...
if not exist .env (
    echo.
    echo ERROR: .env file not found
    echo.
    echo Setup:
    echo   1. copy env.example .env
    echo   2. Edit .env and add GRID_API_KEY and GRID_WORKER_NAME
    echo   3. Run this script again
    pause
    exit /b 1
)
echo    Configuration file found

REM Clean up old volumes that don't match configuration
echo [5/6] Cleaning up old volumes...
docker volume ls -q | findstr /C:"comfy-bridge_input" >nul 2>&1
if not errorlevel 1 (
    echo    Removing old input volume...
    docker volume rm comfy-bridge_input >nul 2>&1
)
docker volume ls -q | findstr /C:"comfy-bridge_cache" >nul 2>&1
if not errorlevel 1 (
    echo    Removing old cache volume...
    docker volume rm comfy-bridge_cache >nul 2>&1
)

REM Start containers with BuildKit for cache mounts
echo [6/6] Starting worker containers...
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1
docker-compose up -d

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start worker
    echo Check error messages above for details.
    echo.
    echo Common issues:
    echo   - Port 5000 or 8188 already in use
    echo   - Insufficient system resources
    echo   - Docker not fully started
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Worker started successfully!
echo ========================================
echo.

REM Build Electron app and create desktop shortcut
echo Building desktop app...
cd management-ui-nextjs

REM Check if Node.js is installed
where node >nul 2>&1
if errorlevel 1 (
    echo    Node.js not found - skipping desktop app build
    echo    Install Node.js from https://nodejs.org/ to enable desktop app
    goto :skip_electron
)

REM Check if npm is installed
where npm >nul 2>&1
if errorlevel 1 (
    echo    npm not found - skipping desktop app build
    goto :skip_electron
)

echo    Installing dependencies...
call npm install --silent >nul 2>&1
if errorlevel 1 (
    echo    Failed to install dependencies - skipping desktop app build
    goto :skip_electron
)

echo    Compiling Electron app...
call npm run electron:compile >nul 2>&1
if errorlevel 1 (
    echo    Failed to compile Electron app - skipping desktop app build
    goto :skip_electron
)

echo    Building Electron executable...
call npm run electron:pack >nul 2>&1
if errorlevel 1 (
    echo    Failed to build Electron app - skipping desktop app build
    goto :skip_electron
)

REM Find the built executable
set ELECTRON_EXE=
if exist "dist\win-unpacked\AI Power Grid Manager.exe" (
    set ELECTRON_EXE=dist\win-unpacked\AI Power Grid Manager.exe
) else if exist "dist\AI Power Grid Manager.exe" (
    set ELECTRON_EXE=dist\AI Power Grid Manager.exe
)

if "!ELECTRON_EXE!"=="" (
    echo    Could not find built Electron executable
    goto :skip_electron
)

REM Get desktop path
for /f "tokens=*" %%a in ('powershell -Command "[Environment]::GetFolderPath('Desktop')"') do set DESKTOP=%%a

if "!DESKTOP!"=="" (
    echo    Could not determine desktop path
    goto :skip_electron
)

REM Create desktop shortcut using PowerShell
echo    Creating desktop shortcut...
set "EXE_PATH=%CD%\!ELECTRON_EXE!"
set "WORK_DIR=%CD%\dist\win-unpacked"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\AI Power Grid Manager.lnk'); $Shortcut.TargetPath = '%EXE_PATH%'; $Shortcut.WorkingDirectory = '%WORK_DIR%'; $Shortcut.Description = 'AI Power Grid Worker Management UI'; $Shortcut.Save()" >nul 2>&1

if errorlevel 1 (
    echo    Failed to create desktop shortcut
) else (
    echo    Desktop shortcut created successfully!
)

:skip_electron
cd ..

echo.
echo Management UI: http://localhost:5000
echo.
echo Next steps:
echo   1. Use the desktop app shortcut (if created) OR
echo   2. Open http://localhost:5000 in your browser
echo   3. Select and download models
echo   4. Click "Start Hosting" to begin earning
echo.
echo Commands:
echo   View logs: docker-compose logs -f
echo   Stop worker: docker-compose down
echo.
pause
