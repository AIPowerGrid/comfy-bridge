FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed (example: gcc, libffi-dev, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential net-tools htop \
    && rm -rf /var/lib/apt/lists/*

# Copy only the necessary files
COPY requirements.txt ./
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Entrypoint: check that .env exists and start the bridge
CMD ["/bin/sh", "-c", "if [ ! -f .env ]; then echo 'ERROR: .env file is missing in /app. Use --env-file or mount the file.'; exit 1; fi; python start_bridge.py"] 