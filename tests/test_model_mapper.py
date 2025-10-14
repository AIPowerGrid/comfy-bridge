import pytest
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.model_mapper import initialize_model_mapper, get_horde_models


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