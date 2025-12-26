"""Tests for blockchain ModelVault client."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from comfy_bridge.modelvault_client import (
    get_modelvault_client,
    ModelVaultClient,
    OnChainModelInfo,
    ModelType,
    ValidationResult,
)


class TestModelVaultClient:
    """Test ModelVault blockchain client."""
    
    @pytest.fixture
    def mock_contract(self):
        """Create a mock Web3 contract."""
        contract = Mock()
        contract.functions = Mock()
        return contract
    
    @pytest.fixture
    def client_disabled(self):
        """Create a disabled client (no web3)."""
        return ModelVaultClient(enabled=False)
    
    @pytest.fixture
    def client_enabled(self, mock_contract):
        """Create an enabled client with mocked contract."""
        with patch('comfy_bridge.modelvault_client.Web3') as mock_web3:
            mock_w3 = Mock()
            mock_w3.eth.contract.return_value = mock_contract
            mock_web3.HTTPProvider.return_value = Mock()
            mock_web3.return_value = mock_w3
            
            client = ModelVaultClient(
                enabled=True,
                rpc_url="http://localhost:8545",
                contract_address="0x0000000000000000000000000000000000000000"
            )
            client._contract = mock_contract
            return client
    
    def test_client_disabled_returns_permissive_validation(self, client_disabled):
        """Disabled client should allow all operations."""
        result = client_disabled.validate_params(
            file_name="test.safetensors",
            steps=100,
            cfg=10.0
        )
        assert result.is_valid is True
        assert result.reason == ""
    
    def test_client_enabled_without_web3_fallsback(self):
        """Client should fallback gracefully if web3 not available."""
        with patch('comfy_bridge.modelvault_client.Web3', None):
            client = get_modelvault_client(enabled=True)
            assert client.enabled is False
    
    def test_fetch_all_models_caching(self, client_enabled, mock_contract):
        """Test that fetch_all_models caches results."""
        # Mock getModelCount
        mock_contract.functions.getModelCount.return_value.call.return_value = 2
        
        # Mock getModel responses
        model1_data = (
            b'\x00' * 32,  # modelHash
            1,  # modelType (IMAGE_MODEL)
            "flux.safetensors",  # fileName
            "FLUX.1-dev",  # name
            "1.0",  # version
            "",  # ipfsCid
            "https://example.com/flux.safetensors",  # downloadUrl
            1000000,  # sizeBytes
            "fp8",  # quantization
            "flux",  # format
            24000,  # vramMB
            "flux_1",  # baseModel
            False,  # inpainting
            True,  # img2img
            False,  # controlnet
            False,  # lora
            True,  # isActive
            False,  # isNSFW
            1234567890,  # timestamp
            "0x" + "0" * 40  # creator
        )
        
        model2_data = (
            b'\x01' * 32,
            2,  # VIDEO_MODEL
            "wan2.2.safetensors",
            "wan2.2-t2v-a14b",
            "2.2",
            "",
            "https://example.com/wan.safetensors",
            2000000,
            "fp16",
            "wan",
            48000,
            "wan_2_2",
            False,
            True,
            False,
            False,
            True,
            False,
            1234567891,
            "0x" + "1" * 40
        )
        
        mock_contract.functions.getModel.return_value.call.side_effect = [
            model1_data,
            model2_data
        ]
        
        # First fetch
        models1 = client_enabled.fetch_all_models()
        assert len(models1) > 0
        
        # Second fetch should use cache
        models2 = client_enabled.fetch_all_models()
        assert models1 == models2
        
        # Force refresh
        models3 = client_enabled.fetch_all_models(force_refresh=True)
        assert len(models3) > 0
    
    def test_validate_params_with_constraints(self, client_enabled, mock_contract):
        """Test parameter validation against model constraints."""
        model_hash = b'\x00' * 32
        
        # Mock hash generation
        with patch.object(client_enabled, 'hash_model', return_value=model_hash):
            # Mock model exists
            with patch.object(client_enabled, 'is_model_registered', return_value=True):
                # Mock getModelByHash returns image model (not video)
                mock_contract.functions.getModelByHash.return_value.call.return_value = (
                    model_hash,
                    1,  # IMAGE_MODEL
                    "test.safetensors",
                    "Test Model",
                    "1.0", "", "", 1000000, "fp8", "flux",
                    24000, "flux_1", False, True, False, False,
                    True, False, 1234567890, "0x" + "0" * 40
                )
                
                # Mock constraints
                mock_contract.functions.getConstraints.return_value.call.return_value = (
                    20,  # stepsMin
                    50,  # stepsMax
                    50,  # cfgMinTenths (5.0)
                    100,  # cfgMaxTenths (10.0)
                    0,  # clipSkip
                    [],  # allowedSamplers
                    [],  # allowedSchedulers
                    True  # exists
                )
                
                # Valid params
                result = client_enabled.validate_params(
                    file_name="test.safetensors",
                    steps=30,
                    cfg=7.0
                )
                assert result.is_valid is True
                
                # Invalid steps (too low)
                result = client_enabled.validate_params(
                    file_name="test.safetensors",
                    steps=10,
                    cfg=7.0
                )
                assert result.is_valid is False
                assert "below min" in result.reason
                
                # Invalid CFG (too high)
                result = client_enabled.validate_params(
                    file_name="test.safetensors",
                    steps=30,
                    cfg=15.0
                )
                assert result.is_valid is False
                assert "exceeds max" in result.reason
    
    def test_video_models_skip_constraints(self, client_enabled, mock_contract):
        """Test that video models skip constraint validation."""
        model_hash = b'\x00' * 32
        
        with patch.object(client_enabled, 'hash_model', return_value=model_hash):
            with patch.object(client_enabled, 'is_model_registered', return_value=True):
                # Mock video model
                mock_contract.functions.getModelByHash.return_value.call.return_value = (
                    model_hash,
                    2,  # VIDEO_MODEL
                    "wan.safetensors",
                    "WAN 2.2",
                    "2.2", "", "", 2000000, "fp16", "wan",
                    48000, "wan_2_2", False, True, False, False,
                    True, False, 1234567890, "0x" + "0" * 40
                )
                
                # Video models should pass validation regardless of params
                result = client_enabled.validate_params(
                    file_name="wan.safetensors",
                    steps=1000,  # Extreme value
                    cfg=100.0    # Extreme value
                )
                assert result.is_valid is True
    
    def test_unregistered_model_passes_validation(self, client_enabled):
        """Test that unregistered models pass validation (allow workflow-based models)."""
        with patch.object(client_enabled, 'is_model_registered', return_value=False):
            result = client_enabled.validate_params(
                file_name="unregistered.safetensors",
                steps=30,
                cfg=7.0
            )
            # Should pass - models with workflows can still be used
            assert result.is_valid is True
    
    def test_model_type_enum(self):
        """Test ModelType enum values."""
        assert ModelType.TEXT_MODEL == 0
        assert ModelType.IMAGE_MODEL == 1
        assert ModelType.VIDEO_MODEL == 2
        
        # Test to_workflow_type conversion
        assert ModelType.TEXT_MODEL.to_workflow_type() == "text"
        assert ModelType.IMAGE_MODEL.to_workflow_type() == "image"
        assert ModelType.VIDEO_MODEL.to_workflow_type() == "video"
    
    def test_on_chain_model_info_creation(self):
        """Test OnChainModelInfo dataclass."""
        model = OnChainModelInfo(
            model_hash="0x" + "0" * 64,
            model_type=ModelType.IMAGE_MODEL,
            file_name="test.safetensors",
            display_name="Test Model",
            description="A test model",
            is_nsfw=False,
            size_bytes=1000000,
        )
        
        assert model.model_hash == "0x" + "0" * 64
        assert model.model_type == ModelType.IMAGE_MODEL
        assert model.file_name == "test.safetensors"
        assert model.display_name == "Test Model"
        assert model.is_nsfw is False
        
        # Test get_model_id
        model_id = model.get_model_id()
        assert model_id == f"test.safetensors"
    
    def test_find_model_by_name(self, client_enabled, mock_contract):
        """Test finding models by name with various matching strategies."""
        # Setup mock models in cache
        client_enabled._model_cache = {
            "FLUX.1-dev": OnChainModelInfo(
                model_hash="0x00",
                model_type=ModelType.IMAGE_MODEL,
                file_name="flux.safetensors",
                display_name="FLUX.1-dev",
                description="FLUX model",
                is_nsfw=False,
                size_bytes=1000000,
            ),
            "wan2.2-t2v-a14b": OnChainModelInfo(
                model_hash="0x01",
                model_type=ModelType.VIDEO_MODEL,
                file_name="wan.safetensors",
                display_name="wan2.2-t2v-a14b",
                description="WAN video model",
                is_nsfw=False,
                size_bytes=2000000,
            )
        }
        client_enabled._cache_initialized = True
        
        # Exact match
        model = client_enabled.find_model("FLUX.1-dev")
        assert model is not None
        assert model.display_name == "FLUX.1-dev"
        
        # Case-insensitive match
        model = client_enabled.find_model("flux.1-dev")
        assert model is not None
        
        # Partial match
        model = client_enabled.find_model("flux")
        assert model is not None
        
        # Not found
        model = client_enabled.find_model("nonexistent")
        assert model is None
    
    def test_singleton_client(self):
        """Test that get_modelvault_client returns singleton."""
        client1 = get_modelvault_client(enabled=False)
        client2 = get_modelvault_client(enabled=False)
        assert client1 is client2
    
    def test_description_generation(self, client_enabled):
        """Test automatic description generation for models."""
        # FLUX model
        desc = client_enabled._generate_description("FLUX.1-dev")
        assert "FLUX" in desc
        assert "image" in desc.lower()
        
        # WAN video model
        desc = client_enabled._generate_description("wan2.2-t2v-a14b")
        assert "WAN" in desc
        assert "video" in desc.lower() or "Video" in desc
        
        # LTXV model
        desc = client_enabled._generate_description("ltxv")
        assert "LTX" in desc or "ltxv" in desc.lower()


class TestValidationResult:
    """Test ValidationResult dataclass."""
    
    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(is_valid=True, reason="")
        assert result.is_valid is True
        assert result.reason == ""
    
    def test_invalid_result(self):
        """Test invalid validation result with reason."""
        result = ValidationResult(
            is_valid=False,
            reason="Steps exceed maximum"
        )
        assert result.is_valid is False
        assert "Steps exceed maximum" in result.reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

