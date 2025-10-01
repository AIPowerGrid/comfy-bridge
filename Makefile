.PHONY: help build up down logs shell restart clean verify test

# Default target
help:
	@echo "ComfyUI Bridge - Docker Management"
	@echo "=================================="
	@echo ""
	@echo "Available commands:"
	@echo "  make build      - Build the Docker image"
	@echo "  make up         - Start containers in background"
	@echo "  make down       - Stop containers"
	@echo "  make logs       - View container logs (follow mode)"
	@echo "  make shell      - Open shell in running container"
	@echo "  make restart    - Restart containers"
	@echo "  make clean      - Stop containers and remove volumes"
	@echo "  make verify     - Verify setup and configuration"
	@echo "  make test       - Run tests"
	@echo ""

# Build the Docker image
build:
	@echo "Building ComfyUI Bridge Docker image..."
	docker-compose build

# Start containers
up:
	@echo "Starting ComfyUI Bridge..."
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@docker-compose ps

# Stop containers
down:
	@echo "Stopping ComfyUI Bridge..."
	docker-compose down

# View logs
logs:
	@echo "Viewing logs (Ctrl+C to exit)..."
	docker-compose logs -f

# Open shell in container
shell:
	@echo "Opening shell in container..."
	docker-compose exec comfy-bridge /bin/bash

# Restart containers
restart:
	@echo "Restarting containers..."
	docker-compose restart
	@sleep 5
	@docker-compose ps

# Clean everything (including volumes)
clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "Cleaned up successfully"; \
	else \
		echo "Cancelled"; \
	fi

# Verify setup
verify:
	@echo "Running setup verification..."
	@bash verify-setup.sh

# Run tests
test:
	@echo "Running tests..."
	docker-compose exec comfy-bridge pytest tests/

# Check ComfyUI status
status:
	@echo "Checking ComfyUI status..."
	@curl -s http://localhost:8188/system_stats | python -m json.tool || echo "ComfyUI not responding"

# Pull latest ComfyUI
update-comfyui:
	@echo "Updating ComfyUI in container..."
	docker-compose exec comfy-bridge sh -c "cd /app/ComfyUI && git pull"
	@echo "Restarting container..."
	docker-compose restart

# View ComfyUI logs
comfyui-logs:
	@echo "Viewing ComfyUI logs..."
	docker-compose exec comfy-bridge cat /tmp/comfyui.log

# GPU check
gpu-check:
	@echo "Checking GPU availability..."
	docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi || \
		echo "GPU not available or nvidia-docker not configured"

