import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.bridge import ComfyUIBridge


class TestComfyUIBridge:
    """Test the ComfyUIBridge class."""

    @pytest.fixture
    def bridge(self):
        """Create a ComfyUIBridge instance for testing."""
        with patch('comfy_bridge.bridge.APIClient'), \
             patch('comfy_bridge.api_client.httpx.AsyncClient'):
            return ComfyUIBridge()

    def test_init(self, bridge):
        """Test ComfyUIBridge initialization."""
        assert bridge.supported_models == []
        assert bridge.processing_jobs == set()
        assert bridge._workflow_cache == {}
        assert bridge._model_cache == {}

    def test_reset_job_flags(self, bridge):
        """Test _reset_job_flags method."""
        # Set some flags
        bridge._first_history_check = True
        bridge._filesystem_checked = True
        bridge._debug_logged = True
        
        # Reset flags
        bridge._reset_job_flags()
        
        # Check flags are removed
        assert not hasattr(bridge, '_first_history_check')
        assert not hasattr(bridge, '_filesystem_checked')
        assert not hasattr(bridge, '_debug_logged')

    @pytest.mark.asyncio
    async def test_process_job_polling_timeout(self, bridge):
        """Test _process_job_polling with timeout."""
        with patch('comfy_bridge.bridge.time.time', side_effect=[0, 601]):  # 601 seconds
            with pytest.raises(Exception, match="Job timed out after 600s"):
                await bridge._process_job_polling("test-prompt", "test-job", "test-model")

    @pytest.mark.asyncio
    async def test_check_filesystem_fallback_no_files(self, bridge):
        """Test _check_filesystem_fallback with no files found."""
        with patch('comfy_bridge.bridge.glob.glob', return_value=[]):
            result = await bridge._check_filesystem_fallback("test-job")
            assert result is None

    @pytest.mark.asyncio
    async def test_check_filesystem_fallback_small_file(self, bridge):
        """Test _check_filesystem_fallback with small file."""
        small_file = "/tmp/small_video.mp4"
        
        with patch('comfy_bridge.bridge.glob.glob', return_value=[small_file]), \
             patch('comfy_bridge.bridge.Path') as mock_path:
            
            mock_path_instance = MagicMock()
            mock_path_instance.suffix.lower.return_value = '.mp4'
            mock_path_instance.name = "small_video.mp4"
            mock_path.return_value = mock_path_instance
            
            with patch('comfy_bridge.bridge.os.path.getsize', return_value=50 * 1024):  # 50KB
                result = await bridge._check_filesystem_fallback("test-job")
                assert result is None

    @pytest.mark.asyncio
    async def test_process_completed_outputs_image(self, bridge):
        """Test _process_completed_outputs with image output."""
        outputs = {
            "3": {
                "images": [{"filename": "test.png"}]
            }
        }

        # Mock ComfyUI client response
        mock_response = MagicMock()
        mock_response.content = b"fake image content" * 1000
        mock_response.raise_for_status.return_value = None

        bridge.comfy.get = AsyncMock(return_value=mock_response)

        result = await bridge._process_completed_outputs(outputs, "test-model")

        assert result is not None
        assert result[0] == mock_response.content
        assert result[1] == "image"
        assert result[2] == "test.png"

    @pytest.mark.asyncio
    async def test_process_completed_outputs_wan2_model_skips_images(self, bridge):
        """Test _process_completed_outputs skips images for WAN2 models."""
        outputs = {
            "3": {
                "images": [{"filename": "test.png"}]
            }
        }

        result = await bridge._process_completed_outputs(outputs, "wan2-model")

        assert result is None

    @pytest.mark.asyncio
    async def test_listen_comfyui_logs_success(self, bridge):
        """Test listen_comfyui_logs with successful connection."""
        with patch('comfy_bridge.bridge.websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
            mock_websocket.__aexit__ = AsyncMock(return_value=None)
            
            # Mock message data
            mock_message = '{"type": "progress", "data": {"value": 5, "max": 10}}'
            mock_websocket.__aiter__ = AsyncMock(return_value=iter([mock_message]))
            
            mock_connect.return_value = mock_websocket

            # Start the task and cancel it quickly
            task = asyncio.create_task(bridge.listen_comfyui_logs("test-prompt"))
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_listen_comfyui_logs_connection_error(self, bridge):
        """Test listen_comfyui_logs with connection error."""
        with patch('comfy_bridge.bridge.websockets.connect', side_effect=Exception("Connection failed")):
            # Should not raise an exception
            await bridge.listen_comfyui_logs("test-prompt")

    @pytest.mark.asyncio
    async def test_process_once_no_job(self, bridge):
        """Test process_once with no job available."""
        bridge.api.pop_job = AsyncMock(return_value=None)

        await bridge.process_once()

        # Should return without processing
        assert len(bridge.processing_jobs) == 0

    @pytest.mark.asyncio
    async def test_process_once_duplicate_job(self, bridge):
        """Test process_once with duplicate job."""
        mock_job = {"id": "test-job-123", "model": "test-model"}
        bridge.api.pop_job = AsyncMock(return_value=mock_job)
        
        # Add job to processing set
        bridge.processing_jobs.add("test-job-123")

        await bridge.process_once()

        # Job should not be processed again
        bridge.api.submit_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_once_error_cleanup(self, bridge):
        """Test process_once error handling and cleanup."""
        mock_job = {"id": "test-job-123", "model": "test-model"}
        bridge.api.pop_job = AsyncMock(return_value=mock_job)
        bridge.api.cancel_job = AsyncMock()

        # Mock workflow building to raise an exception
        with patch('comfy_bridge.bridge.build_workflow', side_effect=Exception("Workflow error")):
            await bridge.process_once()

        # Verify cleanup
        assert "test-job-123" not in bridge.processing_jobs
        bridge.api.cancel_job.assert_called_once_with("test-job-123")

    @pytest.mark.asyncio
    async def test_cleanup(self, bridge):
        """Test cleanup method."""
        bridge.comfy.aclose = AsyncMock()
        bridge.api.client.aclose = AsyncMock()

        await bridge.cleanup()

        bridge.comfy.aclose.assert_called_once()
        bridge.api.client.aclose.assert_called_once()