#!/bin/bash
# Verification script for ComfyUI Bridge Docker deployment

echo "================================================"
echo "  ComfyUI Bridge - Setup Verification"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_docker() {
    echo -n "Checking Docker installation... "
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
        docker --version
    else
        echo -e "${RED}✗${NC}"
        echo "Docker is not installed. Please install Docker first."
        exit 1
    fi
}

check_docker_compose() {
    echo -n "Checking Docker Compose... "
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
        docker-compose --version 2>/dev/null || docker compose version
    else
        echo -e "${RED}✗${NC}"
        echo "Docker Compose is not installed."
        exit 1
    fi
}

check_nvidia_docker() {
    echo -n "Checking NVIDIA Docker support... "
    if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
        echo "GPU support is available"
    else
        echo -e "${YELLOW}⚠${NC}"
        echo "GPU support not detected. The bridge will run in CPU mode (slower)."
        echo "For GPU support, install nvidia-container-toolkit"
    fi
}

check_env_file() {
    echo -n "Checking environment configuration... "
    if [ -f ".env" ]; then
        echo -e "${GREEN}✓${NC}"
        if grep -q "GRID_API_KEY=your_api_key_here" .env || ! grep -q "GRID_API_KEY=" .env; then
            echo -e "${YELLOW}⚠${NC} WARNING: GRID_API_KEY not configured in .env"
            echo "  Please edit .env and set your API key"
        else
            echo "  API key is configured"
        fi
    else
        echo -e "${YELLOW}⚠${NC}"
        echo "  .env file not found. Creating from env.example..."
        if [ -f "env.example" ]; then
            cp env.example .env
            echo "  Created .env - please edit it and add your GRID_API_KEY"
        else
            echo -e "${RED}✗${NC} env.example not found"
            exit 1
        fi
    fi
}

check_workflows() {
    echo -n "Checking workflow files... "
    if [ -d "workflows" ] && [ "$(ls -A workflows/*.json 2>/dev/null)" ]; then
        echo -e "${GREEN}✓${NC}"
        echo "  Found $(ls -1 workflows/*.json 2>/dev/null | wc -l) workflow files"
    else
        echo -e "${YELLOW}⚠${NC}"
        echo "  No workflow files found in workflows/"
    fi
}

check_running_container() {
    echo -n "Checking if container is running... "
    if docker ps | grep -q comfy-bridge; then
        echo -e "${GREEN}✓${NC}"
        echo "  Container is running"
        
        # Check health
        health=$(docker inspect --format='{{.State.Health.Status}}' comfy-bridge 2>/dev/null)
        if [ "$health" = "healthy" ]; then
            echo -e "  Health status: ${GREEN}$health${NC}"
        else
            echo -e "  Health status: ${YELLOW}$health${NC}"
        fi
    else
        echo -e "${YELLOW}⚠${NC}"
        echo "  Container is not running"
    fi
}

test_comfyui() {
    echo -n "Testing ComfyUI connection... "
    if curl -s http://localhost:8188/system_stats > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        echo "  ComfyUI is accessible at http://localhost:8188"
    else
        echo -e "${RED}✗${NC}"
        echo "  Cannot connect to ComfyUI"
        echo "  Make sure the container is running: docker-compose up -d"
    fi
}

# Run checks
echo "Running setup verification..."
echo ""

check_docker
echo ""

check_docker_compose
echo ""

check_nvidia_docker
echo ""

check_env_file
echo ""

check_workflows
echo ""

check_running_container
echo ""

test_comfyui
echo ""

echo "================================================"
echo "  Verification Complete"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Make sure .env has your GRID_API_KEY configured"
echo "  2. Start the container: docker-compose up -d"
echo "  3. View logs: docker-compose logs -f"
echo "  4. Access ComfyUI: http://localhost:8188"
echo ""
echo "For more information, see DOCKER.md"

