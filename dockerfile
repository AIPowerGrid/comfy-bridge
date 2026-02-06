# Dockerfile

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 comfyui_bridge_worker && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home comfyui_bridge_worker && \
    chown -R comfyui_bridge_worker:comfyui_bridge_worker /app

USER comfyui_bridge_worker

ENTRYPOINT ["python", "-m", "bridge.cli"]