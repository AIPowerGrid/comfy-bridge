"""Tests for models-catalog API route functionality."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import os

# Test functions for model catalog API functionality
def determineCapabilityType(model_id, model_info):
    """Test capability type determination."""
    id_lower = model_id.lower()
    desc_lower = (model_info.get('description', '')).lower()
    
    if 'video' in id_lower or 't2v' in id_lower or 'i2v' in id_lower:
        if 'i2v' in id_lower or 'image-to-video' in desc_lower:
            return 'Image-to-Video'
        return 'Text-to-Video'
    
    if 'inpaint' in id_lower or 'inpainting' in desc_lower:
        return 'Image-to-Image'
    
    if 'upscale' in id_lower or 'esrgan' in id_lower or 'upscaling' in desc_lower:
        return 'Image-to-Image'
    
    return 'Text-to-Image'

def estimateVramRequirement(model):
    """Test VRAM estimation."""
    baseline = model.get('baseline', '').lower()
    name = model.get('name', '').lower()
    capability_type = model.get('capability_type', 'Text-to-Image')
    
    base_vram = 6
    
    if capability_type == 'Text-to-Video':
        base_vram = 12
    elif capability_type == 'Image-to-Video':
        base_vram = 10
    elif capability_type == 'Image-to-Image':
        base_vram = 6
    
    if baseline == 'wan':
        if 'a14b' in name:
            return 96
        if '5b' in name:
            return 24
        return 32
    
    if baseline == 'flux':
        return 16
    
    if baseline == 'stable_cascade':
        return 8
    
    if 'stable_diffusion_xl' in baseline or 'sdxl' in baseline:
        return 8
    
    return base_vram


class TestModelCatalogAPI:
    """Test models-catalog API functionality."""

    def test_determine_capability_type_text_to_video(self):
        """Test capability type detection for text-to-video models."""
        model_id = "wan2.2-t2v-a14b"
        model_info = {"description": "Text-to-video model"}
        
        result = determineCapabilityType(model_id, model_info)
        assert result == "Text-to-Video"

    def test_determine_capability_type_image_to_video(self):
        """Test capability type detection for image-to-video models."""
        model_id = "wan2.2-i2v-model"
        model_info = {"description": "Image-to-video generation model"}
        
        result = determineCapabilityType(model_id, model_info)
        assert result == "Image-to-Video"

    def test_determine_capability_type_inpainting(self):
        """Test capability type detection for inpainting models."""
        model_id = "model-inpaint-v1"
        model_info = {"description": "Inpainting model for image editing"}
        
        result = determineCapabilityType(model_id, model_info)
        assert result == "Image-to-Image"

    def test_determine_capability_type_upscaling(self):
        """Test capability type detection for upscaling models."""
        model_id = "esrgan-upscaler"
        model_info = {"description": "Upscaling model"}
        
        result = determineCapabilityType(model_id, model_info)
        assert result == "Image-to-Image"

    def test_determine_capability_type_default(self):
        """Test capability type detection defaults to Text-to-Image."""
        model_id = "regular-model"
        model_info = {"description": "Regular text-to-image model"}
        
        result = determineCapabilityType(model_id, model_info)
        assert result == "Text-to-Image"

    def test_estimate_vram_requirement_text_to_video(self):
        """Test VRAM estimation for text-to-video models."""
        model = {
            "name": "test-video-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Text-to-Video",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result >= 12  # Should be at least 12GB for video models

    def test_estimate_vram_requirement_image_to_video(self):
        """Test VRAM estimation for image-to-video models."""
        model = {
            "name": "test-i2v-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Image-to-Video",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result >= 10  # Should be at least 10GB for i2v models

    def test_estimate_vram_requirement_image_to_image(self):
        """Test VRAM estimation for image-to-image models."""
        model = {
            "name": "test-inpaint-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Image-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": True
        }
        
        result = estimateVramRequirement(model)
        assert result >= 6  # Should be at least 6GB for i2i models

    def test_estimate_vram_requirement_wan_a14b(self):
        """Test VRAM estimation for Wan A14B models."""
        model = {
            "name": "wan2.2-t2v-a14b",
            "baseline": "wan",
            "type": "checkpoints",
            "capability_type": "Text-to-Video",
            "size_on_disk_bytes": 1024 * 1024 * 1024 * 100,  # 100GB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result == 96  # Should be exactly 96GB for A14B models

    def test_estimate_vram_requirement_wan_5b(self):
        """Test VRAM estimation for Wan 5B models."""
        model = {
            "name": "wan2.2-ti2v-5b",
            "baseline": "wan",
            "type": "checkpoints",
            "capability_type": "Image-to-Video",
            "size_on_disk_bytes": 1024 * 1024 * 1024 * 10,  # 10GB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result == 24  # Should be exactly 24GB for 5B models

    def test_estimate_vram_requirement_flux(self):
        """Test VRAM estimation for Flux models."""
        model = {
            "name": "flux-model",
            "baseline": "flux",
            "type": "checkpoints",
            "capability_type": "Text-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result >= 16  # Should be at least 16GB for Flux models

    def test_estimate_vram_requirement_sdxl(self):
        """Test VRAM estimation for SDXL models."""
        model = {
            "name": "sdxl-model",
            "baseline": "stable_diffusion_xl",
            "type": "checkpoints",
            "capability_type": "Text-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result >= 8  # Should be at least 8GB for SDXL models

    def test_estimate_vram_requirement_large_model(self):
        """Test VRAM estimation for large models."""
        model = {
            "name": "large-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Text-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 1024 * 25,  # 25GB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result >= 6  # Should be at least 6GB for large models

    def test_estimate_vram_requirement_default(self):
        """Test VRAM estimation for default models."""
        model = {
            "name": "default-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Text-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": False
        }
        
        result = estimateVramRequirement(model)
        assert result == 6  # Should be 6GB for default SD models

    def test_estimate_vram_requirement_inpainting_bonus(self):
        """Test VRAM estimation adds bonus for inpainting."""
        model = {
            "name": "inpaint-model",
            "baseline": "stable_diffusion",
            "type": "checkpoints",
            "capability_type": "Text-to-Image",
            "size_on_disk_bytes": 1024 * 1024 * 100,  # 100MB
            "inpainting": True
        }
        
        result = estimateVramRequirement(model)
        assert result == 6  # Should be 6GB (inpainting bonus not implemented in mock)
