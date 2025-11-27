"""Tests for comfy_bridge.utils module."""

import pytest
import base64
from pathlib import Path
from comfy_bridge.utils import generate_seed, encode_media, encode_image, encode_video


class TestGenerateSeed:
    """Test the generate_seed function."""

    def test_generate_seed_with_valid_int(self):
        """Test seed generation with valid integer."""
        result = generate_seed(12345)
        assert result == 12345

    def test_generate_seed_with_zero(self):
        """Test seed generation with zero (should generate random)."""
        result = generate_seed(0)
        assert isinstance(result, int)
        assert result > 0

    def test_generate_seed_with_negative(self):
        """Test seed generation with negative number (should generate random)."""
        result = generate_seed(-1)
        assert isinstance(result, int)
        assert result > 0

    def test_generate_seed_with_string(self):
        """Test seed generation with string (should generate random)."""
        result = generate_seed("invalid")
        assert isinstance(result, int)
        assert result > 0

    def test_generate_seed_with_none(self):
        """Test seed generation with None (should generate random)."""
        result = generate_seed(None)
        assert isinstance(result, int)
        assert result > 0


class TestEncodeMedia:
    """Test the encode_media function."""

    def test_encode_media_with_bytes(self):
        """Test encoding bytes data."""
        test_data = b"test data"
        result = encode_media(test_data)
        expected = base64.b64encode(test_data).decode()
        assert result == expected

    def test_encode_media_with_bytearray(self):
        """Test encoding bytearray data."""
        test_data = bytearray(b"test data")
        result = encode_media(test_data)
        expected = base64.b64encode(test_data).decode()
        assert result == expected

    def test_encode_media_with_file_path(self, temp_file):
        """Test encoding file path."""
        result = encode_media(str(temp_file))
        expected = base64.b64encode(b"test content").decode()
        assert result == expected

    def test_encode_media_with_path_object(self, temp_file):
        """Test encoding Path object."""
        result = encode_media(temp_file)
        expected = base64.b64encode(b"test content").decode()
        assert result == expected

    def test_encode_media_with_nonexistent_file(self):
        """Test encoding non-existent file raises error."""
        with pytest.raises(ValueError, match="Unable to read"):
            encode_media("/nonexistent/file.txt")

    def test_encode_media_with_image_file(self, temp_image_file):
        """Test encoding image file."""
        result = encode_media(temp_image_file, "image")
        # Should be able to decode back to original bytes
        decoded = base64.b64decode(result)
        assert decoded == temp_image_file.read_bytes()

    def test_encode_media_custom_media_type(self, temp_file):
        """Test encoding with custom media type."""
        result = encode_media(temp_file, "custom")
        expected = base64.b64encode(b"test content").decode()
        assert result == expected


class TestLegacyFunctions:
    """Test legacy encode functions."""

    def test_encode_image_with_bytes(self):
        """Test encode_image with bytes."""
        test_data = b"image data"
        result = encode_image(test_data)
        expected = base64.b64encode(test_data).decode()
        assert result == expected

    def test_encode_image_with_file(self, temp_file):
        """Test encode_image with file."""
        result = encode_image(str(temp_file))
        expected = base64.b64encode(b"test content").decode()
        assert result == expected

    def test_encode_video_with_bytes(self):
        """Test encode_video with bytes."""
        test_data = b"video data"
        result = encode_video(test_data)
        expected = base64.b64encode(test_data).decode()
        assert result == expected

    def test_encode_video_with_file(self, temp_file):
        """Test encode_video with file."""
        result = encode_video(str(temp_file))
        expected = base64.b64encode(b"test content").decode()
        assert result == expected

