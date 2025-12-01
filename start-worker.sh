#!/bin/bash
set -e

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check for root/admin privileges
if [ "$EUID" -ne 0 ]; then 
    echo "Requesting administrator privileges..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sudo "$0" "$@"
        exit $?
    else
        sudo "$0" "$@"
        exit $?
    fi
fi

echo ""
echo "========================================"
echo " AI Power Grid Worker - Starting..."
echo "========================================"
echo ""

# Check disk space (50GB minimum)
echo "[1/5] Checking disk space..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    FREE_SPACE_GB=$(df -g . | awk 'NR==2 {print $4}')
else
    FREE_SPACE_GB=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
fi

if [ "$FREE_SPACE_GB" -lt 50 ]; then
    echo ""
    echo -e "${RED}ERROR: Insufficient disk space${NC}"
    echo "Required: 50 GB minimum"
    echo "Available: ${FREE_SPACE_GB} GB"
    echo ""
    echo "Free up disk space and try again."
    exit 1
fi
echo -e "    ${GREEN}✓${NC} Disk space OK (${FREE_SPACE_GB} GB available)"

# Check Docker installation
echo "[2/5] Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo ""
    echo -e "${RED}ERROR: Docker is not installed${NC}"
    echo ""
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        echo "Or run: brew install --cask docker"
        echo ""
        echo "After installation, start Docker Desktop and run this script again."
        echo ""
        read -p "Open Docker download page? (y/n): " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && open "https://www.docker.com/products/docker-desktop"
    else
        echo "Install Docker:"
        echo "  Ubuntu/Debian: sudo apt-get install -y docker.io docker-compose"
        echo "  Fedora/RHEL: sudo dnf install -y docker docker-compose"
        echo ""
        echo "Then:"
        echo "  sudo systemctl start docker"
        echo "  sudo systemctl enable docker"
        echo "  sudo usermod -aG docker $USER"
        echo ""
        echo "After installation, log out and back in, then run this script again."
    fi
    exit 1
fi
echo -e "    ${GREEN}✓${NC} Docker found"

# Check Docker is running
echo "[3/5] Checking Docker is running..."
if ! docker info > /dev/null 2>&1; then
    echo ""
    echo -e "${RED}ERROR: Docker is not running${NC}"
    echo ""
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Start Docker Desktop from Applications."
        echo ""
        read -p "Start Docker Desktop now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open -a Docker
            echo "Waiting for Docker to start..."
            for i in {1..12}; do
                sleep 5
                docker info > /dev/null 2>&1 && break
                echo -n "."
            done
            echo ""
            if ! docker info > /dev/null 2>&1; then
                echo -e "${RED}Docker did not start. Start it manually and try again.${NC}"
                exit 1
            fi
            echo -e "    ${GREEN}✓${NC} Docker is running"
        else
            exit 1
        fi
    else
        echo "Start Docker service: sudo systemctl start docker"
        echo ""
        read -p "Start Docker now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if systemctl start docker; then
                echo -e "    ${GREEN}✓${NC} Docker started"
            else
                echo -e "${RED}Failed to start Docker. Run manually: sudo systemctl start docker${NC}"
                exit 1
            fi
        else
            exit 1
        fi
    fi
else
    echo -e "    ${GREEN}✓${NC} Docker is running"
fi

# Check .env file
echo "[4/5] Checking configuration..."
if [ ! -f .env ]; then
    echo ""
    echo -e "${RED}ERROR: .env file not found${NC}"
    echo ""
    echo "Setup:"
    echo "  1. cp env.example .env"
    echo "  2. Edit .env and add GRID_API_KEY and GRID_WORKER_NAME"
    echo "  3. Run this script again"
    exit 1
fi
echo -e "    ${GREEN}✓${NC} Configuration file found"

# Clean up old volumes that don't match configuration
echo "[5/6] Cleaning up old volumes..."
if docker volume ls -q | grep -q "^comfy-bridge_input$"; then
    echo "    Removing old input volume..."
    docker volume rm comfy-bridge_input > /dev/null 2>&1 || true
fi
if docker volume ls -q | grep -q "^comfy-bridge_cache$"; then
    echo "    Removing old cache volume..."
    docker volume rm comfy-bridge_cache > /dev/null 2>&1 || true
fi

# Start containers with BuildKit for cache mounts
echo "[6/6] Starting worker containers..."
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker-compose up -d

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Failed to start worker${NC}"
    echo "Check error messages above for details."
    echo ""
    echo "Common issues:"
    echo "  - Port 5000 or 8188 already in use"
    echo "  - Insufficient system resources"
    echo "  - Docker not fully started"
    exit 1
fi

echo ""
echo "========================================"
echo -e " ${GREEN}Worker started successfully!${NC}"
echo "========================================"
echo ""

# Build Electron app and create desktop shortcut
echo "Building desktop app..."
cd management-ui-nextjs

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "    ${YELLOW}Node.js not found - skipping desktop app build${NC}"
    echo "    Install Node.js from https://nodejs.org/ to enable desktop app"
    cd ..
else
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        echo -e "    ${YELLOW}npm not found - skipping desktop app build${NC}"
        cd ..
    else
        echo "    Installing dependencies..."
        if ! npm install --silent > /dev/null 2>&1; then
            echo -e "    ${YELLOW}Failed to install dependencies - skipping desktop app build${NC}"
            cd ..
        else
            echo "    Compiling Electron app..."
            if ! npm run electron:compile > /dev/null 2>&1; then
                echo -e "    ${YELLOW}Failed to compile Electron app - skipping desktop app build${NC}"
                cd ..
            else
                echo "    Building Electron executable..."
                if ! npm run electron:pack > /dev/null 2>&1; then
                    echo -e "    ${YELLOW}Failed to build Electron app - skipping desktop app build${NC}"
                    cd ..
                else

        # Find the built executable
        ELECTRON_EXE=""
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if [ -d "dist/mac/AI Power Grid Manager.app" ]; then
                ELECTRON_EXE="dist/mac/AI Power Grid Manager.app"
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if [ -f "dist/AI Power Grid Manager.AppImage" ]; then
                ELECTRON_EXE="dist/AI Power Grid Manager.AppImage"
            elif [ -f "dist/linux-unpacked/aipg-model-manager" ]; then
                ELECTRON_EXE="dist/linux-unpacked/aipg-model-manager"
            fi
        fi

                    # Find the built executable
                    ELECTRON_EXE=""
                    if [[ "$OSTYPE" == "darwin"* ]]; then
                        if [ -d "dist/mac/AI Power Grid Manager.app" ]; then
                            ELECTRON_EXE="dist/mac/AI Power Grid Manager.app"
                        fi
                    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                        if [ -f "dist/AI Power Grid Manager.AppImage" ]; then
                            ELECTRON_EXE="dist/AI Power Grid Manager.AppImage"
                        elif [ -f "dist/linux-unpacked/aipg-model-manager" ]; then
                            ELECTRON_EXE="dist/linux-unpacked/aipg-model-manager"
                        fi
                    fi

                    if [ -z "$ELECTRON_EXE" ]; then
                        echo -e "    ${YELLOW}Could not find built Electron executable${NC}"
                        cd ..
                    else
                        # Create desktop entry/launcher
                        if [[ "$OSTYPE" == "darwin"* ]]; then
                            DESKTOP="$HOME/Desktop"
                            if [ -d "$DESKTOP" ]; then
                                echo "    Creating desktop shortcut..."
                                FULL_PATH="$(cd "$(dirname "$ELECTRON_EXE")" && pwd)/$(basename "$ELECTRON_EXE")"
                                osascript -e "tell application \"Finder\" to make alias file at POSIX file \"$DESKTOP\" to POSIX file \"$FULL_PATH\"" 2>/dev/null && {
                                    echo -e "    ${GREEN}Desktop shortcut created successfully!${NC}"
                                } || echo -e "    ${YELLOW}Failed to create desktop shortcut${NC}"
                            fi
                        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                            DESKTOP="$HOME/Desktop"
                            if [ -d "$DESKTOP" ]; then
                                echo "    Creating desktop shortcut..."
                                FULL_PATH="$(cd "$(dirname "$ELECTRON_EXE")" && pwd)/$(basename "$ELECTRON_EXE")"
                                ICON_PATH="$(pwd)/public/logo.png"
                                cat > "$DESKTOP/AI Power Grid Manager.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Power Grid Manager
Comment=AI Power Grid Worker Management UI
Exec="$FULL_PATH"
Icon=$ICON_PATH
Terminal=false
Categories=Utility;
EOF
                                chmod +x "$DESKTOP/AI Power Grid Manager.desktop"
                                echo -e "    ${GREEN}Desktop shortcut created successfully!${NC}"
                            fi
                        fi
                        cd ..
                    fi
                fi
            fi
        fi
    fi
fi

echo ""
echo "Management UI: http://localhost:5000"
echo ""
echo "Next steps:"
echo "  1. Use the desktop app shortcut (if created) OR"
echo "  2. Open http://localhost:5000 in your browser"
echo "  3. Select and download models"
echo "  4. Click 'Start Hosting' to begin earning"
echo ""
echo "Commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop worker: docker-compose down"
echo ""
