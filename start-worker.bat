@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ========================================
echo  AI Power Grid Worker - Starting...
echo ========================================
echo.

REM Check disk space (50GB minimum)
echo [1/4] Checking disk space...
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
echo [2/4] Checking Docker installation...
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
echo [3/4] Checking Docker is running...
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
echo [4/4] Checking configuration...
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

REM Start containers
echo.
echo Starting worker containers...
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
echo Management UI: http://localhost:5000
echo.
echo Next steps:
echo   1. Open http://localhost:5000 in your browser
echo   2. Select and download models
echo   3. Click "Start Hosting" to begin earning
echo.
echo Commands:
echo   View logs: docker-compose logs -f
echo   Stop worker: docker-compose down
echo.
pause
