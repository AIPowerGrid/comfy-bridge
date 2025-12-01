"""Tests for PayloadBuilder class."""

import pytest
from unittest.mock import patch, MagicMock
from comfy_bridge.payload_builder import PayloadBuilder, BYTES_PER_MB, MAX_B64_SIZE_MB


class TestPayloadBuilder:
    """Test the PayloadBuilder class."""

    @pytest.fixture
    def payload_builder(self):
        """Create a PayloadBuilder instance for testing."""
        return PayloadBuilder()

    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes."""
        return b"fake image data"

    @pytest.fixture
    def sample_video_bytes(self):
        """Create sample video bytes."""
        return b"fake video data" * 1000

    @pytest.fixture
    def mock_job(self):
        """Create a mock job for testing."""
        return {
            "id": "test-job-123",
            "payload": {
                "seed": 12345
            }
        }

    def test_build_standard_payload_image(self, payload_builder, mock_job, sample_image_bytes):
        """Test building standard payload for image."""
        payload = payload_builder.build_payload(
            mock_job, sample_image_bytes, "image", "test.png"
        )

        assert payload["id"] == "test-job-123"
        assert payload["state"] == "ok"
        assert payload["seed"] == 12345
        assert payload["media_type"] == "image"
        assert "generation" in payload
        assert isinstance(payload["generation"], str)

    def test_build_standard_payload_video(self, payload_builder, mock_job, sample_video_bytes):
        """Test building standard payload for video."""
        payload = payload_builder.build_payload(
            mock_job, sample_video_bytes, "video", "test.mp4"
        )

        assert payload["id"] == "test-job-123"
        assert payload["state"] == "ok"
        assert payload["seed"] == 12345
        assert payload["media_type"] == "video"
        assert payload["form"] == "video"
        assert payload["type"] == "video"
        assert payload["filename"] == "test.mp4"
        assert "generation" in payload

    def test_build_video_r2_payload_with_r2_upload_url(self, payload_builder, mock_job, sample_video_bytes):
        """Test building R2 payload when r2_upload URL is provided."""
        mock_job["r2_upload"] = "https://r2.example.com/upload"
        
        payload = payload_builder.build_payload(
            mock_job, sample_video_bytes, "video", "test.webm"
        )

        assert payload["id"] == "test-job-123"
        assert payload["media_type"] == "video"
        # WebM is a valid video extension, so it should be preserved
        assert payload["filename"] == "test.webm"
        assert "r2_uploads" in payload
        assert len(payload["r2_uploads"]) == 1
        assert payload["r2_uploads"][0]["url"] == "https://r2.example.com/upload"
        assert "generation" in payload

    def test_build_video_r2_payload_with_r2_uploads_array(self, payload_builder, mock_job, sample_video_bytes):
        """Test building R2 payload when r2_uploads array is provided."""
        mock_job["r2_upload"] = "https://r2.example.com/upload"
        mock_job["r2_uploads"] = [
            {"url": "https://r2.example.com/upload1"},
            {"url": "https://r2.example.com/upload2"}
        ]
        
        payload = payload_builder.build_payload(
            mock_job, sample_video_bytes, "video", "test.avi"
        )

        assert payload["r2_uploads"] == mock_job["r2_uploads"]
        assert len(payload["r2_uploads"]) == 2

    def test_build_video_r2_payload_no_r2_info(self, payload_builder, mock_job, sample_video_bytes):
        """Test building R2 payload when no R2 info is provided."""
        # No r2_upload or r2_uploads
        payload = payload_builder.build_payload(
            mock_job, sample_video_bytes, "video", "test.mov"
        )

        assert payload["media_type"] == "video"
        assert "generation" in payload
        assert "r2_uploads" not in payload

    def test_ensure_mp4_extension_adds_extension(self, payload_builder, mock_job):
        """Test that _ensure_mp4_extension adds .mp4 if missing."""
        result = payload_builder._ensure_mp4_extension("test", "job-123")
        assert result == "test.mp4"

    def test_ensure_mp4_extension_preserves_existing(self, payload_builder, mock_job):
        """Test that _ensure_mp4_extension preserves existing video extensions."""
        for ext in [".mp4", ".webm", ".avi", ".mov"]:
            result = payload_builder._ensure_mp4_extension(f"test{ext}", "job-123")
            assert result == f"test{ext}"

    def test_ensure_mp4_extension_handles_empty_filename(self, payload_builder):
        """Test that _ensure_mp4_extension handles empty filename."""
        result = payload_builder._ensure_mp4_extension("", "job-123")
        assert result == "video_job-123.mp4"

    def test_ensure_mp4_extension_handles_none_filename(self, payload_builder):
        """Test that _ensure_mp4_extension handles None filename."""
        result = payload_builder._ensure_mp4_extension(None, "job-123")
        assert result == "video_job-123.mp4"

    @patch('comfy_bridge.payload_builder.logger')
    def test_large_base64_warning(self, mock_logger, payload_builder, mock_job):
        """Test that large base64 payloads trigger a warning."""
        # Create large video bytes to exceed threshold
        large_video_bytes = b"x" * (MAX_B64_SIZE_MB * BYTES_PER_MB * 2)
        mock_job["r2_upload"] = "https://r2.example.com/upload"
        
        payload_builder.build_payload(
            mock_job, large_video_bytes, "video", "test.mp4"
        )

        # Check that warning was logged
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if "Base64 video size" in str(call)]
        assert len(warning_calls) > 0

    def test_seed_defaults_to_zero(self, payload_builder, sample_image_bytes):
        """Test that seed defaults to 0 if not provided."""
        job = {
            "id": "test-job-123",
            "payload": {}
        }
        
        payload = payload_builder.build_payload(
            job, sample_image_bytes, "image", "test.png"
        )

        assert payload["seed"] == 0

    def test_seed_from_payload(self, payload_builder, sample_image_bytes):
        """Test that seed is extracted from job payload."""
        job = {
            "id": "test-job-123",
            "payload": {
                "seed": 99999
            }
        }
        
        payload = payload_builder.build_payload(
            job, sample_image_bytes, "image", "test.png"
        )

        assert payload["seed"] == 99999

