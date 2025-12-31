"""Pytest configuration and fixtures for comfy-bridge tests."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
import os
from pathlib import Path


# Prevent .env file from being loaded during tests
@pytest.fixture(scope="session", autouse=True)
def prevent_env_loading():
    """Prevent .env file from being loaded during tests."""
    # This runs before any test and prevents dotenv from loading .env
    # Tests should explicitly set environment variables they need
    pass


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return {
        "GRID_API_KEY": "test-api-key",
        "GRID_WORKER_NAME": "test-worker",
        "COMFYUI_URL": "http://localhost:8000",
        "GRID_API_URL": "https://api.test.com",
        "NSFW": False,
        "THREADS": 1,
        "MAX_PIXELS": 20971520,
        "WORKFLOW_DIR": "/test/workflows",
        "WORKFLOW_FILE": "test.json",
        "COMFYUI_OUTPUT_DIR": "/test/output",
    }


@pytest.fixture
def mock_job():
    """Mock job data for testing."""
    return {
        "id": "test-job-123",
        "model": "test-model",
        "params": {
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg_scale": 7.5,
            "seed": 12345,
        },
        "payload": {
            "prompt": "test prompt",
            "negative_prompt": "test negative",
            "seed": 12345,
        },
        "r2_upload": "https://test.com/upload",
        "r2_uploads": [],
    }


@pytest.fixture
def mock_workflow():
    """Mock workflow data for testing."""
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 12345,
                "steps": 20,
                "cfg": 7.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "test-model.safetensors",
            },
        },
    }


@pytest.fixture
def mock_comfyui_response():
    """Mock ComfyUI API response."""
    return {
        "prompt_id": "test-prompt-123",
        "number": 1,
        "node_errors": {},
    }


@pytest.fixture
def mock_history_response():
    """Mock ComfyUI history response."""
    return {
        "test-prompt-123": {
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
            "outputs": {
                "3": {
                    "images": [
                        {
                            "filename": "test-image.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ],
                }
            },
        }
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    client = AsyncMock(spec=AsyncClient)
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    return test_file


@pytest.fixture
def temp_image_file(tmp_path):
    """Create a temporary image file for testing."""
    # Create a simple PNG file (minimal valid PNG)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    image_file = tmp_path / "test.png"
    image_file.write_bytes(png_data)
    return image_file

