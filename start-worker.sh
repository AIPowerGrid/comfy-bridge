#!/bin/bash
set -e

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo "========================================"
echo " AI Power Grid Worker - Starting..."
echo "========================================"
echo ""

# Check disk space (50GB minimum)
echo "[1/4] Checking disk space..."
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
echo "[2/4] Checking Docker installation..."
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
echo "[3/4] Checking Docker is running..."
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
        read -p "Start Docker now? (requires sudo) (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if sudo systemctl start docker; then
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
echo "[4/4] Checking configuration..."
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

# Start containers
echo ""
echo "Starting worker containers..."
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
echo "Management UI: http://localhost:5000"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:5000 in your browser"
echo "  2. Select and download models"
echo "  3. Click 'Start Hosting' to begin earning"
echo ""
echo "Commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop worker: docker-compose down"
echo ""
