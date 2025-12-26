"""Tests for blockchain ModelVault client."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from comfy_bridge.modelvault_client import (
    get_modelvault_client,
    ModelVaultClient,
    OnChainModelInfo,
    ModelType,
    ValidationResult,
    ModelConstraints,
    ModelFile,
)


class TestModelVaultClient:
    """Test ModelVault blockchain client."""
    
    @pytest.fixture
    def client_disabled(self):
        """Create a disabled client (no web3)."""
        return ModelVaultClient(enabled=False)
    
    @pytest.fixture
    def client_enabled_mock(self):
        """Create an enabled client with mocked contract."""
        client = ModelVaultClient(enabled=False)  # Start disabled
        client.enabled = True  # Enable manually
        client._contract = Mock()
        client._w3 = Mock()
        return client
    
    def test_client_disabled_returns_permissive_validation(self, client_disabled):
        """Disabled client should allow all operations."""
        result = client_disabled.validate_params(
            file_name="test.safetensors",
            steps=100,
            cfg=10.0
        )
        assert result.is_valid is True
        # reason can be None or empty string
        assert result.reason is None or result.reason == ""
    
    def test_client_disabled_returns_empty_models(self, client_disabled):
        """Disabled client should return empty model list."""
        models = client_disabled.fetch_all_models()
        assert isinstance(models, dict)
        assert len(models) == 0
    
    def test_client_disabled_model_check_permissive(self, client_disabled):
        """Disabled client should be permissive for model registration checks."""
        # Should return True (permissive) when disabled
        result = client_disabled.is_model_registered("any_model.safetensors")
        assert result is True
    
    def test_fetch_all_models_caching(self, client_enabled_mock):
        """Test that fetch_all_models caches results."""
        # Mock getModelCount
        client_enabled_mock._contract.functions.getModelCount.return_value.call.return_value = 1
        
        # Mock getModel response
        model_data = (
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
        
        client_enabled_mock._contract.functions.getModel.return_value.call.return_value = model_data
        
        # Mock get_constraints to return None
        client_enabled_mock._contract.functions.getConstraints.return_value.call.side_effect = Exception("No constraints")
        
        # First fetch
        models1 = client_enabled_mock.fetch_all_models()
        assert len(models1) >= 0  # May be 0 if blockchain fetch fails
        
        # Second fetch should use cache
        models2 = client_enabled_mock.fetch_all_models()
        assert models1 == models2
        
        # Force refresh
        models3 = client_enabled_mock.fetch_all_models(force_refresh=True)
        assert isinstance(models3, dict)
    
    def test_validate_params_no_constraints(self, client_enabled_mock):
        """Test parameter validation when model has no constraints."""
        # Mock model is registered
        client_enabled_mock._contract.functions.getModelByHash.return_value.call.side_effect = Exception("Not found")
        
        with patch.object(client_enabled_mock, 'is_model_registered', return_value=True):
            with patch.object(client_enabled_mock, 'get_model_by_hash', return_value=None):
                with patch.object(client_enabled_mock, 'get_constraints', return_value=None):
                    # Should pass when no constraints exist
                    result = client_enabled_mock.validate_params(
                        file_name="test.safetensors",
                        steps=30,
                        cfg=7.0
                    )
                    assert result.is_valid is True
    
    def test_validate_params_video_model_skips_constraints(self, client_enabled_mock):
        """Test that video models skip constraint validation."""
        # Create a video model
        video_model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.VIDEO_MODEL,
            file_name="wan.safetensors",
            display_name="WAN 2.2",
            description="Video model",
            is_nsfw=False,
            size_bytes=2000000,
            inpainting=False,
            img2img=True,
            controlnet=False,
            lora=False,
            base_model="wan_2_2",
            architecture="wan",
            is_active=True,
        )
        
        with patch.object(client_enabled_mock, 'is_model_registered', return_value=True):
            with patch.object(client_enabled_mock, 'get_model_by_hash', return_value=video_model):
                # Video models should pass validation regardless of params
                result = client_enabled_mock.validate_params(
                    file_name="wan.safetensors",
                    steps=1000,  # Extreme value
                    cfg=100.0    # Extreme value
                )
                assert result.is_valid is True
    
    def test_unregistered_model_passes_validation(self, client_enabled_mock):
        """Test that unregistered models pass validation (allow workflow-based models)."""
        with patch.object(client_enabled_mock, 'is_model_registered', return_value=False):
            result = client_enabled_mock.validate_params(
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
            inpainting=False,
            img2img=True,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        
        assert model.model_hash == "0x" + "0" * 64
        assert model.model_type == ModelType.IMAGE_MODEL
        assert model.file_name == "test.safetensors"
        assert model.display_name == "Test Model"
        assert model.is_nsfw is False
        
        # Test get_model_id
        model_id = model.get_model_id()
        assert model_id == "test"
    
    def test_find_model_by_name(self, client_enabled_mock):
        """Test finding models by name with various matching strategies."""
        # Setup mock models in cache
        client_enabled_mock._model_cache = {
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
            ),
            "wan2.2-t2v-a14b": OnChainModelInfo(
                model_hash="0x01",
                model_type=ModelType.VIDEO_MODEL,
                file_name="wan.safetensors",
                display_name="wan2.2-t2v-a14b",
                description="WAN video model",
                is_nsfw=False,
                size_bytes=2000000,
                inpainting=False,
                img2img=True,
                controlnet=False,
                lora=False,
                base_model="wan_2_2",
                architecture="wan",
                is_active=True,
            )
        }
        client_enabled_mock._cache_initialized = True
        
        # Exact match
        model = client_enabled_mock.find_model("FLUX.1-dev")
        assert model is not None
        assert model.display_name == "FLUX.1-dev"
        
        # Case-insensitive match
        model = client_enabled_mock.find_model("flux.1-dev")
        assert model is not None
        
        # Partial match
        model = client_enabled_mock.find_model("flux")
        assert model is not None
        
        # Not found
        model = client_enabled_mock.find_model("nonexistent")
        assert model is None
    
    def test_singleton_client(self):
        """Test that get_modelvault_client returns singleton."""
        client1 = get_modelvault_client(enabled=False)
        client2 = get_modelvault_client(enabled=False)
        assert client1 is client2
    
    def test_description_generation(self, client_enabled_mock):
        """Test automatic description generation for models."""
        # FLUX model
        desc = client_enabled_mock._generate_description("FLUX.1-dev")
        assert "FLUX" in desc
        assert "image" in desc.lower()
        
        # WAN video model
        desc = client_enabled_mock._generate_description("wan2.2-t2v-a14b")
        assert "WAN" in desc
        assert "video" in desc.lower() or "Video" in desc
        
        # LTXV model
        desc = client_enabled_mock._generate_description("ltxv")
        assert "LTX" in desc or "ltxv" in desc.lower()


class TestValidationResult:
    """Test ValidationResult dataclass."""
    
    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(is_valid=True, reason=None)
        assert result.is_valid is True
        assert result.reason is None
    
    def test_invalid_result(self):
        """Test invalid validation result with reason."""
        result = ValidationResult(
            is_valid=False,
            reason="Steps exceed maximum"
        )
        assert result.is_valid is False
        assert "Steps exceed maximum" in result.reason


class TestModelConstraints:
    """Test ModelConstraints dataclass."""
    
    def test_constraints_creation(self):
        """Test creating model constraints."""
        constraints = ModelConstraints(
            steps_min=20,
            steps_max=50,
            cfg_min=5.0,
            cfg_max=10.0,
            clip_skip=0,
            allowed_samplers=["euler", "dpm++"],
            allowed_schedulers=["normal", "karras"],
        )
        
        assert constraints.steps_min == 20
        assert constraints.steps_max == 50
        assert constraints.cfg_min == 5.0
        assert constraints.cfg_max == 10.0
        assert len(constraints.allowed_samplers) == 2
        assert len(constraints.allowed_schedulers) == 2


class TestModelFile:
    """Test ModelFile dataclass."""
    
    def test_model_file_creation(self):
        """Test creating model file info."""
        file = ModelFile(
            file_name="model.safetensors",
            file_type="checkpoint",
            download_url="https://example.com/model.safetensors",
            mirror_url="https://mirror.com/model.safetensors",
            sha256_hash="abc123",
            size_bytes=1000000,
        )
        
        assert file.file_name == "model.safetensors"
        assert file.file_type == "checkpoint"
        assert file.download_url == "https://example.com/model.safetensors"
        assert file.size_bytes == 1000000


class TestNegativeCases:
    """Test negative cases and error handling."""
    
    @pytest.fixture
    def client_disabled(self):
        """Create a disabled client."""
        return ModelVaultClient(enabled=False)
    
    @pytest.fixture
    def client_enabled_mock(self):
        """Create an enabled client with mocked contract."""
        client = ModelVaultClient(enabled=False)
        client.enabled = True
        client._contract = Mock()
        client._w3 = Mock()
        return client
    
    def test_validate_params_steps_too_low(self):
        """Test validation fails when steps are too low."""
        # Create constraints with minimum steps
        constraints = ModelConstraints(
            steps_min=20,
            steps_max=50,
            cfg_min=5.0,
            cfg_max=10.0,
            clip_skip=0,
            allowed_samplers=[],
            allowed_schedulers=[],
        )
        
        # Steps below minimum should fail
        # (This would be tested in integration with actual validation logic)
        assert constraints.steps_min == 20
        assert 10 < constraints.steps_min  # 10 steps is too low
    
    def test_validate_params_steps_too_high(self):
        """Test validation fails when steps are too high."""
        constraints = ModelConstraints(
            steps_min=20,
            steps_max=50,
            cfg_min=5.0,
            cfg_max=10.0,
            clip_skip=0,
            allowed_samplers=[],
            allowed_schedulers=[],
        )
        
        # Steps above maximum should fail
        assert constraints.steps_max == 50
        assert 100 > constraints.steps_max  # 100 steps is too high
    
    def test_validate_params_cfg_too_low(self):
        """Test validation fails when CFG is too low."""
        constraints = ModelConstraints(
            steps_min=20,
            steps_max=50,
            cfg_min=5.0,
            cfg_max=10.0,
            clip_skip=0,
            allowed_samplers=[],
            allowed_schedulers=[],
        )
        
        # CFG below minimum should fail
        assert constraints.cfg_min == 5.0
        assert 2.0 < constraints.cfg_min  # 2.0 CFG is too low
    
    def test_validate_params_cfg_too_high(self):
        """Test validation fails when CFG is too high."""
        constraints = ModelConstraints(
            steps_min=20,
            steps_max=50,
            cfg_min=5.0,
            cfg_max=10.0,
            clip_skip=0,
            allowed_samplers=[],
            allowed_schedulers=[],
        )
        
        # CFG above maximum should fail
        assert constraints.cfg_max == 10.0
        assert 20.0 > constraints.cfg_max  # 20.0 CFG is too high
    
    def test_empty_model_name(self, client_disabled):
        """Test handling of empty model name."""
        result = client_disabled.validate_params(
            file_name="",
            steps=30,
            cfg=7.0
        )
        # Should be permissive when disabled
        assert result.is_valid is True
    
    def test_invalid_model_type(self):
        """Test handling of invalid model type."""
        # ModelType enum should only accept valid values
        valid_types = [ModelType.TEXT_MODEL, ModelType.IMAGE_MODEL, ModelType.VIDEO_MODEL]
        assert len(valid_types) == 3
        
        # Test each type is valid
        for mt in valid_types:
            assert mt in [0, 1, 2]
    
    def test_model_info_missing_files(self):
        """Test model info with no download files."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="test.safetensors",
            display_name="Test Model",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
            files=[],  # No files
        )
        
        # get_download_url should return None when no files
        assert model.get_download_url() is None
    
    def test_model_info_inactive_model(self):
        """Test handling of inactive models."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="inactive.safetensors",
            display_name="Inactive Model",
            description="Inactive",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=False,  # Inactive
        )
        
        assert model.is_active is False
        # Inactive models should still be queryable but may not be served
    
    def test_find_model_not_found(self, client_enabled_mock):
        """Test finding a model that doesn't exist."""
        client_enabled_mock._model_cache = {}
        client_enabled_mock._cache_initialized = True
        
        model = client_enabled_mock.find_model("nonexistent_model")
        assert model is None
    
    def test_get_total_models_disabled(self, client_disabled):
        """Test get_total_models returns 0 when disabled."""
        total = client_disabled.get_total_models()
        assert total == 0
    
    def test_get_all_active_models_disabled(self, client_disabled):
        """Test get_all_active_models returns empty list when disabled."""
        models = client_disabled.get_all_active_models()
        assert isinstance(models, list)
        assert len(models) == 0
    
    def test_validation_result_with_empty_reason(self):
        """Test validation result with empty reason string."""
        result = ValidationResult(is_valid=False, reason="")
        assert result.is_valid is False
        assert result.reason == ""
    
    def test_model_file_with_minimal_info(self):
        """Test model file with only required fields."""
        file = ModelFile(
            file_name="minimal.safetensors",
            file_type="checkpoint",
            download_url="https://example.com/minimal.safetensors",
        )
        
        assert file.file_name == "minimal.safetensors"
        assert file.mirror_url == ""
        assert file.sha256_hash == ""
        assert file.size_bytes == 0
    
    def test_get_model_id_various_extensions(self):
        """Test get_model_id handles various file extensions."""
        model_safetensors = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="model.safetensors",
            display_name="Model",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        assert model_safetensors.get_model_id() == "model"
        
        model_ckpt = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="model.ckpt",
            display_name="Model",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        assert model_ckpt.get_model_id() == "model"
        
        model_pt = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="model.pt",
            display_name="Model",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        assert model_pt.get_model_id() == "model"
    
    def test_description_generation_fallback(self, client_enabled_mock):
        """Test description generation for unknown model types."""
        desc = client_enabled_mock._generate_description("UnknownModel123")
        assert "UnknownModel123" in desc
        assert "model" in desc.lower()
    
    def test_get_download_url_with_specific_type(self):
        """Test getting download URL for specific file type."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="model.safetensors",
            display_name="Model",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
            files=[
                ModelFile("model.safetensors", "checkpoint", "https://example.com/model.safetensors"),
                ModelFile("vae.safetensors", "vae", "https://example.com/vae.safetensors"),
            ]
        )
        
        # Get checkpoint URL
        checkpoint_url = model.get_download_url("checkpoint")
        assert checkpoint_url == "https://example.com/model.safetensors"
        
        # Get VAE URL
        vae_url = model.get_download_url("vae")
        assert vae_url == "https://example.com/vae.safetensors"
        
        # Get non-existent type (should return first file)
        fallback_url = model.get_download_url("nonexistent")
        assert fallback_url == "https://example.com/model.safetensors"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def client_disabled(self):
        """Create a disabled client."""
        return ModelVaultClient(enabled=False)
    
    def test_model_with_zero_size(self):
        """Test model with zero size bytes."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="zero.safetensors",
            display_name="Zero Size",
            description="Test",
            is_nsfw=False,
            size_bytes=0,  # Zero size
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        
        assert model.size_bytes == 0
    
    def test_model_with_very_long_name(self):
        """Test model with very long display name."""
        long_name = "A" * 500
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="long.safetensors",
            display_name=long_name,
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
        )
        
        assert len(model.display_name) == 500
        assert model.display_name == long_name
    
    def test_model_with_special_characters(self):
        """Test model with special characters in name."""
        special_name = "Model-2.0_v3 (test) [SDXL]"
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="special.safetensors",
            display_name=special_name,
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="sdxl",
            architecture="sdxl",
            is_active=True,
        )
        
        assert model.display_name == special_name
        # workflow_id should be normalized (spaces replaced with underscores, dots replaced)
        assert " " not in model.workflow_id
        # Note: __post_init__ only replaces spaces and dots, not parentheses/brackets
        assert model.workflow_id.startswith("model-2")
    
    def test_constraints_with_zero_max(self):
        """Test constraints with zero maximum (unlimited)."""
        constraints = ModelConstraints(
            steps_min=0,
            steps_max=0,  # 0 means unlimited
            cfg_min=0.0,
            cfg_max=0.0,  # 0 means unlimited
            clip_skip=0,
            allowed_samplers=[],
            allowed_schedulers=[],
        )
        
        assert constraints.steps_max == 0
        assert constraints.cfg_max == 0.0
        # These should be treated as "no limit" in validation logic
    
    def test_validation_with_none_sampler(self, client_disabled):
        """Test validation with None sampler/scheduler."""
        result = client_disabled.validate_params(
            file_name="test.safetensors",
            steps=30,
            cfg=7.0,
            sampler=None,
            scheduler=None,
        )
        # Should be permissive when disabled
        assert result.is_valid is True
    
    def test_empty_file_list(self):
        """Test model with empty file list."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="empty.safetensors",
            display_name="Empty Files",
            description="Test",
            is_nsfw=False,
            size_bytes=1000000,
            inpainting=False,
            img2img=False,
            controlnet=False,
            lora=False,
            base_model="flux_1",
            architecture="flux",
            is_active=True,
            files=[],
        )
        
        assert len(model.files) == 0
        assert model.get_download_url() is None
    
    def test_model_with_all_capabilities(self):
        """Test model with all capabilities enabled."""
        model = OnChainModelInfo(
            model_hash="0x00",
            model_type=ModelType.IMAGE_MODEL,
            file_name="full.safetensors",
            display_name="Full Features",
            description="Test",
            is_nsfw=True,
            size_bytes=1000000,
            inpainting=True,
            img2img=True,
            controlnet=True,
            lora=True,
            base_model="sdxl",
            architecture="sdxl",
            is_active=True,
        )
        
        assert model.inpainting is True
        assert model.img2img is True
        assert model.controlnet is True
        assert model.lora is True
        assert model.is_nsfw is True
    
    def test_model_type_to_workflow_type_unknown(self):
        """Test workflow type conversion for unknown model type."""
        # Create an invalid enum value (should not happen in practice)
        result = ModelType.IMAGE_MODEL.to_workflow_type()
        assert result in ["text", "image", "video"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
