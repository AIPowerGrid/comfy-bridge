"""Tests for streaming-preview surface added to APIClient.

Covers the path that forwards ComfyUI's binary b_preview frames upstream
to the Grid API, plus throttled progress reporting. Both must fail silently
on any error — a dropped preview must never break a job.
"""

import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

from bridge.api_client import APIClient


@pytest.fixture
def api_client():
    with patch('bridge.api_client.Settings') as mock_settings:
        mock_settings.GRID_API_URL = "https://test.api.com"
        mock_settings.GRID_API_KEY = "test-key"
        mock_settings.GRID_WORKER_NAME = "test-worker"
        mock_settings.MAX_PIXELS = 20_971_520
        mock_settings.NSFW = False
        mock_settings.THREADS = 1
        mock_settings.GRID_MODELS = ["model1"]
        mock_settings.validate.return_value = None
        return APIClient()


# ============ send_preview ============


@pytest.mark.asyncio
async def test_send_preview_posts_raw_bytes_with_step_header(api_client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    api_client.client.post = AsyncMock(return_value=mock_response)

    image_bytes = b"\xff\xd8\xff\xe0fake-jpeg"
    result = await api_client.send_preview(
        job_id="job-abc",
        image_bytes=image_bytes,
        mime="image/jpeg",
        step=12,
    )

    assert result is True
    api_client.client.post.assert_called_once()
    call = api_client.client.post.call_args
    assert call.args[0] == "/v2/generate/preview/job-abc"

    headers = call.kwargs["headers"]
    assert headers["Content-Type"] == "image/jpeg"
    assert headers["X-Step"] == "12"
    assert headers["apikey"] == "test-key"

    # Raw bytes, not base64 or JSON.
    assert call.kwargs["content"] == image_bytes


@pytest.mark.asyncio
async def test_send_preview_skips_empty_payload(api_client):
    api_client.client.post = AsyncMock()
    result = await api_client.send_preview(job_id="x", image_bytes=b"", step=0)
    assert result is False
    api_client.client.post.assert_not_called()


@pytest.mark.asyncio
async def test_send_preview_swallows_404_when_api_lacks_endpoint(api_client):
    fake_response = MagicMock()
    fake_response.status_code = 404
    fake_response.text = "Not Found"
    err = httpx.HTTPStatusError(message="404", request=MagicMock(), response=fake_response)
    api_client.client.post = AsyncMock(side_effect=err)

    result = await api_client.send_preview(job_id="x", image_bytes=b"abc", step=5)
    assert result is False


@pytest.mark.asyncio
async def test_send_preview_swallows_network_errors(api_client):
    api_client.client.post = AsyncMock(side_effect=ConnectionError("dns nope"))
    result = await api_client.send_preview(job_id="x", image_bytes=b"abc")
    assert result is False


@pytest.mark.asyncio
async def test_send_preview_defaults_to_jpeg_and_step_zero(api_client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    api_client.client.post = AsyncMock(return_value=mock_response)

    await api_client.send_preview(job_id="x", image_bytes=b"abc")
    headers = api_client.client.post.call_args.kwargs["headers"]
    assert headers["Content-Type"] == "image/jpeg"
    assert headers["X-Step"] == "0"


@pytest.mark.asyncio
async def test_send_preview_png_mime_is_honored(api_client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    api_client.client.post = AsyncMock(return_value=mock_response)

    await api_client.send_preview(
        job_id="x",
        image_bytes=b"\x89PNG\r\n",
        mime="image/png",
        step=7,
    )
    headers = api_client.client.post.call_args.kwargs["headers"]
    assert headers["Content-Type"] == "image/png"


# ============ update_progress ============


@pytest.mark.asyncio
async def test_update_progress_posts_step_payload(api_client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    api_client.client.post = AsyncMock(return_value=mock_response)

    result = await api_client.update_progress("job-1", current_step=10, total_steps=30)
    assert result is True

    call = api_client.client.post.call_args
    assert call.args[0] == "/v2/generate/progress"
    assert call.kwargs["json"] == {"id": "job-1", "current_step": 10, "total_steps": 30}


@pytest.mark.asyncio
async def test_update_progress_swallows_errors(api_client):
    api_client.client.post = AsyncMock(side_effect=ConnectionError("nope"))
    result = await api_client.update_progress("job-1", 1, 30)
    assert result is False
