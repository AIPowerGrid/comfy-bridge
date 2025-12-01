@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "ROOT_DIR=%CD%"
set "COMPOSE_FILE=%ROOT_DIR%\docker-compose.yml"

if not exist "%COMPOSE_FILE%" (
    echo ERROR: Could not find docker-compose.yml at "%COMPOSE_FILE%"
    echo Ensure you are running this script from the comfy-bridge repository root.
    exit /b 1
)

echo.
echo Starting full stack via docker compose...
echo.

REM Ensure Docker is installed
where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed or not in PATH
    echo Install Docker Desktop from https://www.docker.com/products/docker-desktop/
    exit /b 1
)

REM Detect docker compose command (v2 or legacy)
set "USE_DOCKER_COMPOSE_V2=1"
docker compose version >nul 2>&1
if errorlevel 1 (
    set "USE_DOCKER_COMPOSE_V2=0"
    docker-compose version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Neither "docker compose" nor "docker-compose" is available.
        echo Install Docker Desktop or standalone Docker Compose.
        exit /b 1
    )
)

if "%USE_DOCKER_COMPOSE_V2%"=="1" (
    docker compose -f "%COMPOSE_FILE%" up -d --build
) else (
    docker-compose -f "%COMPOSE_FILE%" up -d --build
)

if errorlevel 1 (
    echo ERROR: Failed to run docker compose
    exit /b 1
)

echo.
echo Docker compose stack is running.
echo.

echo Building Electron desktop app...
echo.

cd management-ui-nextjs

REM Check if Node.js is installed
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed
    echo Install Node.js from https://nodejs.org/
    echo.
    echo Skipping Electron app build...
    exit /b 0
)

REM Check if npm is installed
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm is not installed
    echo Install Node.js (includes npm) from https://nodejs.org/
    echo.
    echo Skipping Electron app build...
    exit /b 0
)

echo Installing dependencies...
call npm install --silent
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Skipping Electron app build...
    exit /b 0
)

echo Compiling Electron app...
call npm run electron:compile
if errorlevel 1 (
    echo ERROR: Failed to compile Electron app
    echo Skipping Electron app build...
    exit /b 0
)

echo Building Electron executable...
call npm run electron:pack
if errorlevel 1 (
    echo ERROR: Failed to build Electron app
    echo Skipping Electron app build...
    exit /b 0
)

REM Find the built executable
set ELECTRON_EXE=
if exist "dist\win-unpacked\AI Power Grid Manager.exe" (
    set ELECTRON_EXE=dist\win-unpacked\AI Power Grid Manager.exe
) else if exist "dist\AI Power Grid Manager.exe" (
    set ELECTRON_EXE=dist\AI Power Grid Manager.exe
)

if "!ELECTRON_EXE!"=="" (
    echo WARNING: Could not find built Electron executable
    echo Skipping desktop shortcut creation...
    exit /b 0
)

REM Get desktop path
for /f "tokens=*" %%a in ('powershell -Command "[Environment]::GetFolderPath('Desktop')"') do set DESKTOP=%%a

if "!DESKTOP!"=="" (
    echo WARNING: Could not determine desktop path
    echo Skipping desktop shortcut creation...
    exit /b 0
)

REM Create desktop shortcut using PowerShell
echo Creating desktop shortcut...
set "EXE_PATH=%CD%\!ELECTRON_EXE!"
set "WORK_DIR=%CD%\dist\win-unpacked"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\AI Power Grid Manager.lnk'); $Shortcut.TargetPath = '%EXE_PATH%'; $Shortcut.WorkingDirectory = '%WORK_DIR%'; $Shortcut.Description = 'AI Power Grid Worker Management UI'; $Shortcut.Save()"

if errorlevel 1 (
    echo WARNING: Failed to create desktop shortcut
    echo You can manually create a shortcut to: %CD%\!ELECTRON_EXE!
) else (
    echo Desktop shortcut created successfully!
    echo Location: %DESKTOP%\AI Power Grid Manager.lnk
)

cd ..

endlocal

