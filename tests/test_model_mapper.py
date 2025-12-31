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
        """Test get_horde_models returns models from workflow map."""
        # Mock the model_mapper singleton to have a workflow_map
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {
                "model1": "workflow1",
                "model2": "workflow2",
            }
            mock_mapper.get_available_horde_models.return_value = ["model1", "model2"]
            
            result = get_horde_models()
            
            # Should return models from workflow map
            assert isinstance(result, list)
            assert len(result) == 2
            assert "model1" in result
            assert "model2" in result

    def test_get_horde_models_no_files(self):
        """Test get_horde_models with no models in workflow map."""
        # Mock the model_mapper singleton with empty workflow_map
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {}
            mock_mapper.get_available_horde_models.return_value = []
            
            result = get_horde_models()
            
            assert result == []

    def test_get_horde_models_returns_workflow_keys(self):
        """Test get_horde_models returns keys from workflow map."""
        # Mock the model_mapper singleton
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {
                "model1": "workflow1",
                "model2": "workflow2",
                "model3": "workflow3",
                "model4": "workflow4",
            }
            mock_mapper.get_available_horde_models.return_value = ["model1", "model2", "model3", "model4"]
            
            result = get_horde_models()
            
            # Should return all workflow map keys
            assert len(result) == 4
            assert "model1" in result
            assert "model2" in result
            assert "model3" in result
            assert "model4" in result

    def test_get_horde_models_blockchain_fallback(self):
        """Test get_horde_models falls back gracefully when blockchain unavailable."""
        # Mock the model_mapper singleton with empty workflow_map (blockchain failed)
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {}
            mock_mapper.chain_models = {}  # No blockchain models
            mock_mapper.get_available_horde_models.return_value = []
            
            result = get_horde_models()
            
            # Should return empty list when blockchain fails
            assert result == []

    def test_get_horde_models_with_blockchain_models(self):
        """Test get_horde_models with blockchain-registered models."""
        # Mock the model_mapper singleton with blockchain models
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            from comfy_bridge.modelvault_client import OnChainModelInfo, ModelType
            
            mock_mapper.chain_models = {
                "FLUX.1-dev": OnChainModelInfo(
                    model_hash="0x00",
                    model_type=ModelType.IMAGE_MODEL,
                    file_name="flux.safetensors",
                    display_name="FLUX.1-dev",
                    description="FLUX model",
                    is_nsfw=False,
                    size_bytes=1000000,
                    inpainting=False,
                    img2img=True,
                    controlnet=False,
                    lora=False,
                    base_model="flux_1",
                    architecture="flux",
                    is_active=True,
                )
            }
            mock_mapper.workflow_map = {"FLUX.1-dev": "flux1.dev"}
            mock_mapper.get_available_horde_models.return_value = ["FLUX.1-dev"]
            
            result = get_horde_models()
            
            # Should return models from workflow map
            assert "FLUX.1-dev" in result

    def test_get_horde_models_with_workflow_file(self):
        """Test get_horde_models with WORKFLOW_FILE environment variable."""
        # Mock the model_mapper singleton
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {
                "model1": "workflow1",
                "model2": "workflow2",
                "model3": "workflow3",
            }
            mock_mapper.get_available_horde_models.return_value = ["model1", "model2", "model3"]
            
            result = get_horde_models()
            
            assert len(result) == 3
            assert "model1" in result
            assert "model2" in result
            assert "model3" in result

    def test_get_horde_models_with_empty_workflow_file(self):
        """Test get_horde_models with empty workflow map."""
        # Mock the model_mapper singleton with empty workflow_map
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {}
            mock_mapper.get_available_horde_models.return_value = []
            
            result = get_horde_models()
            
            assert result == []

    def test_get_horde_models_preserves_model_names(self):
        """Test get_horde_models preserves exact model names from workflow map."""
        # Mock the model_mapper singleton
        with patch('comfy_bridge.model_mapper.model_mapper') as mock_mapper:
            mock_mapper.workflow_map = {
                "FLUX.1-dev": "flux1.dev",
                "wan2.2-t2v-a14b": "wan2.2-t2v-a14b",
                "ltxv": "ltxv",
            }
            mock_mapper.get_available_horde_models.return_value = ["FLUX.1-dev", "wan2.2-t2v-a14b", "ltxv"]
            
            result = get_horde_models()
            
            # Should preserve exact names from workflow map
            assert len(result) == 3
            assert "FLUX.1-dev" in result
            assert "wan2.2-t2v-a14b" in result
            assert "ltxv" in result


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