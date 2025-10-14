import pytest
import os
from unittest.mock import patch
from comfy_bridge.config import Settings


class TestSettings:
    """Test the Settings configuration class."""

    def test_default_values(self):
        """Test default configuration values."""
        # Clear environment variables to test defaults
        with patch.dict(os.environ, {}, clear=True):
            # Reload the module to get fresh defaults
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.GRID_API_KEY == ""
            assert comfy_bridge.config.Settings.GRID_WORKER_NAME == "ComfyUI-Bridge-Worker"
            assert comfy_bridge.config.Settings.COMFYUI_URL == "http://127.0.0.1:8000"
            assert comfy_bridge.config.Settings.GRID_API_URL == "https://api.aipowergrid.io/api"
            assert comfy_bridge.config.Settings.NSFW is False
            assert comfy_bridge.config.Settings.THREADS == 1
            assert comfy_bridge.config.Settings.MAX_PIXELS == 20971520

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        test_env = {
            "GRID_API_KEY": "test-api-key",
            "GRID_WORKER_NAME": "test-worker",
            "COMFYUI_URL": "http://test:9000",
            "GRID_API_URL": "https://test.api.com",
            "GRID_NSFW": "true",
            "GRID_THREADS": "4",
            "GRID_MAX_PIXELS": "41943040"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.GRID_API_KEY == "test-api-key"
            assert comfy_bridge.config.Settings.GRID_WORKER_NAME == "test-worker"
            assert comfy_bridge.config.Settings.COMFYUI_URL == "http://test:9000"
            assert comfy_bridge.config.Settings.GRID_API_URL == "https://test.api.com"
            assert comfy_bridge.config.Settings.NSFW is True
            assert comfy_bridge.config.Settings.THREADS == 4
            assert comfy_bridge.config.Settings.MAX_PIXELS == 41943040

    def test_workflow_models_parsing(self):
        """Test parsing of WORKFLOW_FILE environment variable."""
        test_env = {"WORKFLOW_FILE": "model1,model2,model3"}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.GRID_MODELS == ["model1", "model2", "model3"]

    def test_workflow_models_with_spaces(self):
        """Test parsing of WORKFLOW_FILE with spaces."""
        test_env = {"WORKFLOW_FILE": "model1, model2 , model3"}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.GRID_MODELS == ["model1", "model2", "model3"]

    def test_workflow_models_empty(self):
        """Test parsing of empty WORKFLOW_FILE."""
        test_env = {"WORKFLOW_FILE": ""}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.GRID_MODELS == []

    def test_validate_missing_api_key(self):
        """Test validation with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            with pytest.raises(RuntimeError, match="GRID_API_KEY environment variable is required"):
                comfy_bridge.config.Settings.validate()

    def test_validate_with_api_key(self):
        """Test validation with API key present."""
        test_env = {"GRID_API_KEY": "test-key"}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            # Should not raise an exception
            comfy_bridge.config.Settings.validate()

    def test_nsfw_boolean_conversion(self):
        """Test NSFW boolean conversion."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("", False),
            ("invalid", False)
        ]
        
        for value, expected in test_cases:
            with patch.dict(os.environ, {"GRID_NSFW": value}, clear=True):
                import importlib
                import comfy_bridge.config
                importlib.reload(comfy_bridge.config)
                
                assert comfy_bridge.config.Settings.NSFW == expected

    def test_threads_int_conversion(self):
        """Test THREADS integer conversion."""
        test_env = {"GRID_THREADS": "8"}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.THREADS == 8

    def test_max_pixels_int_conversion(self):
        """Test MAX_PIXELS integer conversion."""
        test_env = {"GRID_MAX_PIXELS": "41943040"}
        
        with patch.dict(os.environ, test_env, clear=True):
            import importlib
            import comfy_bridge.config
            importlib.reload(comfy_bridge.config)
            
            assert comfy_bridge.config.Settings.MAX_PIXELS == 41943040