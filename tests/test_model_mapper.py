import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.model_mapper import (
    initialize_model_mapper, 
    get_horde_models,
    normalize_workflow_name,
    find_workflow_file,
)


class TestModelMapper:
    """Test the model mapper module."""

    @pytest.mark.asyncio
    async def test_initialize_model_mapper_success(self):
        """Test successful model mapper initialization."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None

        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await initialize_model_mapper("http://test:8000")

            # Should make two calls: object_info and model_list
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_initialize_model_mapper_http_error(self):
        """Test model mapper initialization with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("HTTP Error"))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Should not raise an exception
            await initialize_model_mapper("http://test:8000")

    def test_get_horde_models_success(self):
        """Test get_horde_models with successful response."""
        mock_models = ["model1.safetensors", "model2.safetensors", "model3.ckpt"]
        
        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_models
            mock_response.raise_for_status.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = get_horde_models()

            # Should return filtered models
            assert len(result) == 2  # Only .safetensors files
            assert "model1" in result
            assert "model2" in result
            assert "model3" not in result

    def test_get_horde_models_no_files(self):
        """Test get_horde_models with no files."""
        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = get_horde_models()

            assert result == []

    def test_get_horde_models_filter_extensions(self):
        """Test get_horde_models filters file extensions correctly."""
        mock_models = [
            "model1.safetensors",
            "model2.ckpt", 
            "model3.pth",
            "model4.safetensors",
            "model5.txt"
        ]
        
        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_models
            mock_response.raise_for_status.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = get_horde_models()

            # Should only return .safetensors files
            assert len(result) == 2
            assert "model1" in result
            assert "model4" in result

    def test_get_horde_models_http_error(self):
        """Test get_horde_models with HTTP error."""
        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("HTTP Error"))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = get_horde_models()

            assert result == []

    def test_get_horde_models_json_error(self):
        """Test get_horde_models with JSON parsing error."""
        with patch('comfy_bridge.model_mapper.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.raise_for_status.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = get_horde_models()

            assert result == []

    def test_get_horde_models_with_workflow_file(self):
        """Test get_horde_models with WORKFLOW_FILE environment variable."""
        with patch.dict(os.environ, {"WORKFLOW_FILE": "model1,model2,model3"}):
            with patch('comfy_bridge.model_mapper.Settings') as mock_settings:
                mock_settings.WORKFLOW_FILE = "model1,model2,model3"
                mock_settings.GRID_MODELS = ["model1", "model2", "model3"]
                
                result = get_horde_models()

                assert result == ["model1", "model2", "model3"]

    def test_get_horde_models_with_empty_workflow_file(self):
        """Test get_horde_models with empty WORKFLOW_FILE."""
        with patch.dict(os.environ, {"WORKFLOW_FILE": ""}):
            with patch('comfy_bridge.model_mapper.Settings') as mock_settings:
                mock_settings.WORKFLOW_FILE = ""
                mock_settings.GRID_MODELS = []
                
                result = get_horde_models()

                assert result == []

    def test_get_horde_models_with_spaces_in_workflow_file(self):
        """Test get_horde_models with spaces in WORKFLOW_FILE."""
        with patch.dict(os.environ, {"WORKFLOW_FILE": "model1, model2 , model3"}):
            with patch('comfy_bridge.model_mapper.Settings') as mock_settings:
                mock_settings.WORKFLOW_FILE = "model1, model2 , model3"
                mock_settings.GRID_MODELS = ["model1", "model2", "model3"]
                
                result = get_horde_models()

                assert result == ["model1", "model2", "model3"]


class TestNormalizeWorkflowName:
    """Test the normalize_workflow_name function."""

    def test_underscore_to_hyphen(self):
        """Test that underscores are converted to hyphens."""
        assert normalize_workflow_name("flux_1_krea_dev") == "flux-1-krea-dev"

    def test_already_hyphenated(self):
        """Test that already hyphenated names are unchanged."""
        assert normalize_workflow_name("flux-1-krea-dev") == "flux-1-krea-dev"

    def test_mixed_separators(self):
        """Test names with mixed underscores and hyphens."""
        assert normalize_workflow_name("wan2_2-t2v_14b") == "wan2-2-t2v-14b"

    def test_no_separators(self):
        """Test names without separators."""
        assert normalize_workflow_name("ltxv") == "ltxv"

    def test_empty_string(self):
        """Test empty string input."""
        assert normalize_workflow_name("") == ""

    def test_dots_preserved(self):
        """Test that dots are preserved."""
        assert normalize_workflow_name("flux.1_krea_dev") == "flux.1-krea-dev"


class TestFindWorkflowFile:
    """Test the find_workflow_file function with various naming variations."""

    @pytest.fixture
    def temp_workflow_dir(self):
        """Create a temporary directory with test workflow files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test workflow files with various naming conventions
            test_files = [
                "flux.1-krea-dev.json",      # Hyphens
                "wan2.2_ti2v_5B.json",        # Underscores
                "FLUX.1-dev.json",            # Uppercase
                "ltxv.json",                   # Simple name
                "Chroma_final.json",          # Mixed
                "sdxl1.json",                  # Simple
            ]
            for filename in test_files:
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'w') as f:
                    f.write('{}')  # Empty JSON
            yield tmpdir

    def test_exact_match(self, temp_workflow_dir):
        """Test finding file with exact name match."""
        result = find_workflow_file(temp_workflow_dir, "ltxv")
        assert result is not None
        assert os.path.basename(result) == "ltxv.json"

    def test_hyphen_to_underscore(self, temp_workflow_dir):
        """Test finding file when searching with hyphens but file has underscores."""
        # Search for "wan2.2-ti2v-5B" but file is "wan2.2_ti2v_5B.json"
        result = find_workflow_file(temp_workflow_dir, "wan2.2-ti2v-5B")
        assert result is not None
        assert os.path.basename(result) == "wan2.2_ti2v_5B.json"

    def test_underscore_to_hyphen(self, temp_workflow_dir):
        """Test finding file when searching with underscores but file has hyphens."""
        # Search for "flux.1_krea_dev" but file is "flux.1-krea-dev.json"
        result = find_workflow_file(temp_workflow_dir, "flux.1_krea_dev")
        assert result is not None
        assert os.path.basename(result) == "flux.1-krea-dev.json"

    def test_case_insensitive(self, temp_workflow_dir):
        """Test case-insensitive matching."""
        # Search for lowercase but file is uppercase
        result = find_workflow_file(temp_workflow_dir, "flux.1-dev")
        assert result is not None
        # Case may vary by filesystem, so compare case-insensitively
        assert os.path.basename(result).lower() == "flux.1-dev.json"

    def test_case_insensitive_with_normalization(self, temp_workflow_dir):
        """Test case-insensitive matching combined with normalization."""
        # Search for "chroma-final" (lowercase, hyphens) but file is "Chroma_final.json"
        result = find_workflow_file(temp_workflow_dir, "chroma-final")
        assert result is not None
        # Case may vary by filesystem, so compare case-insensitively
        assert os.path.basename(result).lower() == "chroma_final.json"

    def test_with_json_extension(self, temp_workflow_dir):
        """Test that .json extension in input is handled."""
        result = find_workflow_file(temp_workflow_dir, "ltxv.json")
        assert result is not None
        assert os.path.basename(result) == "ltxv.json"

    def test_not_found(self, temp_workflow_dir):
        """Test that None is returned when file is not found."""
        result = find_workflow_file(temp_workflow_dir, "nonexistent-workflow")
        assert result is None

    def test_empty_name(self, temp_workflow_dir):
        """Test that empty name returns None."""
        result = find_workflow_file(temp_workflow_dir, "")
        assert result is None

    def test_none_name(self, temp_workflow_dir):
        """Test that None name returns None."""
        result = find_workflow_file(temp_workflow_dir, None)
        assert result is None

    def test_nonexistent_directory(self):
        """Test that nonexistent directory returns None."""
        result = find_workflow_file("/nonexistent/path", "some-workflow")
        assert result is None

    def test_multiple_variations_priority(self, temp_workflow_dir):
        """Test that exact match takes priority over variations."""
        # Create both variations
        exact_file = os.path.join(temp_workflow_dir, "test-exact.json")
        with open(exact_file, 'w') as f:
            f.write('{}')
        
        result = find_workflow_file(temp_workflow_dir, "test-exact")
        assert result is not None
        assert os.path.basename(result) == "test-exact.json"

    def test_real_world_flux_krea(self, temp_workflow_dir):
        """Test real-world flux.1-krea-dev scenario."""
        # This was the actual bug: mapper had "flux.1_krea_dev" but file was "flux.1-krea-dev.json"
        result = find_workflow_file(temp_workflow_dir, "flux.1_krea_dev")
        assert result is not None
        assert os.path.basename(result) == "flux.1-krea-dev.json"

    def test_real_world_wan_video(self, temp_workflow_dir):
        """Test real-world wan video scenario."""
        # Mapper might have "wan2.2-ti2v-5B" but file is "wan2.2_ti2v_5B.json"
        result = find_workflow_file(temp_workflow_dir, "wan2.2-ti2v-5B")
        assert result is not None
        assert os.path.basename(result) == "wan2.2_ti2v_5B.json"


class TestWorkflowNormalizationIntegration:
    """Integration tests for workflow normalization in the ModelMapper."""

    @pytest.fixture
    def temp_workflow_dir(self):
        """Create a temporary directory with test workflow files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test workflow files
            test_files = [
                "flux.1-krea-dev.json",
                "wan2.2_ti2v_5B.json",
            ]
            for filename in test_files:
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'w') as f:
                    json.dump({"test": True}, f)
            yield tmpdir

    def test_find_handles_all_common_variations(self, temp_workflow_dir):
        """Test that find_workflow_file handles all common naming variations."""
        # All these should find "flux.1-krea-dev.json"
        flux_variations = [
            "flux.1-krea-dev",      # Exact
            "flux.1_krea_dev",      # Underscores
            "FLUX.1-krea-dev",      # Uppercase
            "FLUX.1_krea_dev",      # Uppercase + underscores
            "flux.1-krea-dev.json", # With extension
        ]
        
        for variation in flux_variations:
            result = find_workflow_file(temp_workflow_dir, variation)
            assert result is not None, f"Failed to find file for variation: {variation}"
            # Case may vary by filesystem, so compare case-insensitively
            assert os.path.basename(result).lower() == "flux.1-krea-dev.json"

    def test_find_handles_wan_variations(self, temp_workflow_dir):
        """Test that find_workflow_file handles WAN video naming variations."""
        # All these should find "wan2.2_ti2v_5B.json"
        wan_variations = [
            "wan2.2_ti2v_5B",       # Exact
            "wan2.2-ti2v-5B",       # Hyphens
            "wan2.2_ti2v_5b",       # Lowercase B
            "WAN2.2_ti2v_5B",       # Uppercase WAN
        ]
        
        for variation in wan_variations:
            result = find_workflow_file(temp_workflow_dir, variation)
            assert result is not None, f"Failed to find file for variation: {variation}"
            # Case may vary by filesystem, so compare case-insensitively
            assert os.path.basename(result).lower() == "wan2.2_ti2v_5b.json"