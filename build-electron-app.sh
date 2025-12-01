#!/bin/bash
set -e

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT_DIR="$(pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: Could not find docker-compose.yml at $COMPOSE_FILE"
    echo "Run this script from the comfy-bridge repository root."
    exit 1
fi

echo ""
echo "Starting full stack via docker compose..."
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    echo "Install Docker Desktop or the Docker Engine CLI."
    exit 1
fi

USE_LEGACY_COMPOSE=0
if docker compose version > /dev/null 2>&1; then
    :
elif docker-compose version > /dev/null 2>&1; then
    USE_LEGACY_COMPOSE=1
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' commands are available."
    exit 1
fi

if [ "$USE_LEGACY_COMPOSE" -eq 0 ]; then
    docker compose -f "$COMPOSE_FILE" up -d --build
else
    docker-compose -f "$COMPOSE_FILE" up -d --build
fi

echo ""
echo "Docker compose stack is running."
echo ""

echo "Building Electron desktop app..."
echo ""

cd management-ui-nextjs

echo "Installing dependencies..."
docker run --rm -v "$(pwd):/app" -w /app node:20-alpine sh -c "npm install --silent" || {
    echo -e "${YELLOW}WARNING: Failed to install dependencies${NC}"
    echo "Skipping Electron app build..."
    exit 0
}

echo "Compiling Electron app..."
docker run --rm -v "$(pwd):/app" -w /app node:20-alpine sh -c "npm run electron:compile" || {
    echo -e "${YELLOW}WARNING: Failed to compile Electron app${NC}"
    echo "Skipping Electron app build..."
    exit 0
}

echo "Building Electron executable..."
docker run --rm -v "$(pwd):/app" -w /app node:20-alpine sh -c "npm run electron:pack" || {
    echo -e "${YELLOW}WARNING: Failed to build Electron app${NC}"
    echo "Skipping Electron app build..."
    exit 0
}

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
    echo -e "${YELLOW}WARNING: Could not find built Electron executable${NC}"
    echo "Skipping desktop shortcut creation..."
    exit 0
fi

# Create desktop entry/launcher
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - Create alias on Desktop
    DESKTOP="$HOME/Desktop"
    if [ -d "$DESKTOP" ]; then
        echo "Creating desktop shortcut..."
        FULL_PATH="$(cd "$(dirname "$ELECTRON_EXE")" && pwd)/$(basename "$ELECTRON_EXE")"
        osascript -e "tell application \"Finder\" to make alias file at POSIX file \"$DESKTOP\" to POSIX file \"$FULL_PATH\"" 2>/dev/null || {
            echo -e "${YELLOW}WARNING: Failed to create desktop shortcut${NC}"
            echo "You can manually create an alias to: $FULL_PATH"
        }
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Desktop shortcut created successfully!${NC}"
            echo "Location: $DESKTOP/AI Power Grid Manager"
        fi
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - Create .desktop file
    DESKTOP="$HOME/Desktop"
    if [ -d "$DESKTOP" ]; then
        echo "Creating desktop shortcut..."
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
        echo -e "${GREEN}Desktop shortcut created successfully!${NC}"
        echo "Location: $DESKTOP/AI Power Grid Manager.desktop"
    else
        echo -e "${YELLOW}WARNING: Desktop directory not found${NC}"
    fi
fi

cd ..

