import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.api_client import APIClient


class TestAPIClient:
    """Test the APIClient class."""

    @pytest.fixture
    def api_client(self):
        """Create an APIClient instance for testing."""
        with patch('comfy_bridge.api_client.Settings') as mock_settings:
            mock_settings.GRID_API_URL = "https://test.api.com"
            mock_settings.GRID_API_KEY = "test-key"
            mock_settings.GRID_WORKER_NAME = "test-worker"
            mock_settings.MAX_PIXELS = 20971520
            mock_settings.NSFW = False
            mock_settings.THREADS = 1
            mock_settings.GRID_MODELS = ["model1", "model2"]
            mock_settings.validate.return_value = None
            
            return APIClient()

    def test_init(self, api_client):
        """Test APIClient initialization."""
        assert api_client.headers["apikey"] == "test-key"
        assert api_client.headers["Content-Type"] == "application/json"
        assert api_client._job_cache == {}

    @pytest.mark.asyncio
    async def test_pop_job_success(self, api_client):
        """Test pop_job with successful response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "job-123", "model": "test-model"}
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        result = await api_client.pop_job()

        assert result["id"] == "job-123"
        assert "job-123" in api_client._job_cache

    @pytest.mark.asyncio
    async def test_pop_job_no_job(self, api_client):
        """Test pop_job with no job available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        result = await api_client.pop_job()

        assert result == {}
        assert len(api_client._job_cache) == 0

    @pytest.mark.asyncio
    async def test_pop_job_http_error(self, api_client):
        """Test pop_job with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)
        api_client.client.post = AsyncMock(side_effect=error)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client.pop_job()

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, api_client):
        """Test cancel_job with successful response."""
        job_id = "test-job-123"

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        await api_client.cancel_job(job_id)

        api_client.client.post.assert_called_once_with(
            "/v2/generate/cancel", headers=api_client.headers, json={"id": job_id}
        )

    @pytest.mark.asyncio
    async def test_cancel_job_http_error(self, api_client):
        """Test cancel_job with HTTP error (should not raise)."""
        job_id = "test-job-123"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Job not found"

        error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)
        api_client.client.post = AsyncMock(side_effect=error)

        # Should not raise an exception
        await api_client.cancel_job(job_id)

    @pytest.mark.asyncio
    async def test_submit_result_success(self, api_client):
        """Test submit_result with successful response."""
        payload = {
            "id": "job-123",
            "generation": "base64-data",
            "state": "ok",
            "seed": 12345,
            "media_type": "image"
        }

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        await api_client.submit_result(payload)

        api_client.client.post.assert_called_once_with(
            "/v2/generate/submit", headers=api_client.headers, json=payload
        )

    @pytest.mark.asyncio
    async def test_submit_result_http_error(self, api_client):
        """Test submit_result with HTTP error."""
        payload = {"id": "job-123", "generation": "base64-data", "state": "ok"}

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = ValueError("Not JSON")

        error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)
        api_client.client.post = AsyncMock(side_effect=error)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client.submit_result(payload)

    @pytest.mark.asyncio
    async def test_submit_result_http_error_with_json(self, api_client):
        """Test submit_result with HTTP error containing JSON response."""
        payload = {"id": "job-123", "generation": "base64-data", "state": "ok"}

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"error": "Invalid payload"}

        error = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=mock_response)
        api_client.client.post = AsyncMock(side_effect=error)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client.submit_result(payload)

    @pytest.mark.asyncio
    async def test_submit_result_video(self, api_client):
        """Test submit_result with video payload."""
        payload = {
            "id": "job-123",
            "generation": "base64-data",
            "state": "ok",
            "seed": 12345,
            "filename": "video.mp4",
            "form": "video",
            "type": "video",
            "media_type": "video"
        }

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        await api_client.submit_result(payload)

        api_client.client.post.assert_called_once_with(
            "/v2/generate/submit", headers=api_client.headers, json=payload
        )

    @pytest.mark.asyncio
    async def test_job_cache_management(self, api_client):
        """Test job cache management."""
        # Add job to cache
        api_client._job_cache["job-123"] = {"id": "job-123", "model": "test-model"}

        # Submit result should remove from cache
        payload = {"id": "job-123", "generation": "base64-data", "state": "ok"}

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        api_client.client.post = AsyncMock(return_value=mock_response)

        await api_client.submit_result(payload)

        assert "job-123" not in api_client._job_cache

    @pytest.mark.asyncio
    async def test_pop_job_payload_structure(self, api_client):
        """Test pop_job payload structure."""
        models = ["model1", "model2"]

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        api_client.client.post = AsyncMock(return_value=mock_response)

        await api_client.pop_job(models)

        # Verify payload structure
        call_args = api_client.client.post.call_args
        payload = call_args[1]["json"]

        assert payload["name"] == "test-worker"
        assert payload["models"] == models
        assert payload["max_pixels"] == 20971520
        assert payload["nsfw"] is False
        assert payload["threads"] == 1
        assert payload["amount"] == 1