import pytest
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.workflow import build_workflow, load_workflow_file, process_workflow


class TestBuildWorkflow:
    """Test the build_workflow function."""

    @pytest.fixture
    def mock_job(self):
        """Create a mock job for testing."""
        return {
            "id": "test-job-123",
            "model": "test-model",
            "params": {
                "cfg_scale": 7.5,
                "height": 512,
                "sampler_name": "euler",
                "scheduler": "normal",
                "steps": 20,
                "width": 512
            },
            "payload": {
                "negative_prompt": "test negative",
                "prompt": "test prompt",
                "seed": 12345
            }
        }

    @pytest.mark.asyncio
    async def test_build_workflow_basic(self, mock_job):
        """Test basic workflow building."""
        mock_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "test-model.safetensors",
                },
            },
            "3": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 512,
                    "height": 512,
                    "batch_size": 1,
                },
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "test prompt",
                    "clip": ["2", 1],
                },
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "test negative",
                    "clip": ["2", 1],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            assert result["1"]["inputs"]["seed"] == 12345
            assert result["1"]["inputs"]["steps"] == 20
            assert result["1"]["inputs"]["cfg"] == 7.5
            assert result["4"]["inputs"]["text"] == "test prompt"
            assert result["5"]["inputs"]["text"] == "test negative"

    @pytest.mark.asyncio
    async def test_build_workflow_with_custom_params(self, mock_job):
        """Test workflow building with custom parameters."""
        mock_job["params"]["cfg_scale"] = 9.0
        mock_job["params"]["steps"] = 30

        mock_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "test-model.safetensors",
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            assert result["1"]["inputs"]["cfg"] == 9.0
            assert result["1"]["inputs"]["steps"] == 30

    @pytest.mark.asyncio
    async def test_build_workflow_with_prompt(self, mock_job):
        """Test workflow building with custom prompt."""
        mock_job["payload"]["prompt"] = "custom prompt text"

        mock_template = {
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "test prompt",
                    "clip": ["2", 1],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            assert result["4"]["inputs"]["text"] == "custom prompt text"

    @pytest.mark.asyncio
    async def test_build_workflow_with_seed(self, mock_job):
        """Test workflow building with custom seed."""
        mock_job["payload"]["seed"] = 98765

        mock_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            assert result["1"]["inputs"]["seed"] == 98765

    @pytest.mark.asyncio
    async def test_build_workflow_with_model(self, mock_job):
        """Test workflow building with specific model."""
        mock_job["model"] = "flux-model"

        mock_template = {
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "test-model.safetensors",
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            assert result["2"]["inputs"]["ckpt_name"] == "flux-model.safetensors"

    @pytest.mark.asyncio
    async def test_build_workflow_template_not_found(self, mock_job):
        """Test workflow building when template is not found."""
        with patch('comfy_bridge.workflow.load_workflow_file', return_value=None):
            with pytest.raises(ValueError, match="Workflow template not found"):
                await build_workflow(mock_job)

    @pytest.mark.asyncio
    async def test_build_workflow_empty_template(self, mock_job):
        """Test workflow building with empty template."""
        with patch('comfy_bridge.workflow.load_workflow_file', return_value={}):
            result = await build_workflow(mock_job)
            assert result == {}

    @pytest.mark.asyncio
    async def test_build_workflow_complex_structure(self, mock_job):
        """Test workflow building with complex workflow structure."""
        complex_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "test-model.safetensors",
                },
            },
            "3": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 512,
                    "height": 512,
                    "batch_size": 1,
                },
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "test prompt",
                    "clip": ["2", 1],
                },
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "test negative",
                    "clip": ["2", 1],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=complex_template):
            result = await build_workflow(mock_job)

            # Verify all nodes are present
            assert len(result) == 5
            assert "1" in result
            assert "2" in result
            assert "3" in result
            assert "4" in result
            assert "5" in result

    @pytest.mark.asyncio
    async def test_build_workflow_with_lora(self, mock_job):
        """Test workflow building with LoRA parameters."""
        mock_job["params"]["lora"] = "test-lora"
        mock_job["params"]["lora_strength"] = 0.8

        mock_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            # LoRA parameters should be applied
            assert result["1"]["inputs"]["cfg"] == 7.5

    @pytest.mark.asyncio
    async def test_build_workflow_with_controlnet(self, mock_job):
        """Test workflow building with ControlNet parameters."""
        mock_job["params"]["controlnet"] = "test-controlnet"
        mock_job["params"]["controlnet_strength"] = 0.7

        mock_template = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                },
            },
        }

        with patch('comfy_bridge.workflow.load_workflow_file', return_value=mock_template):
            result = await build_workflow(mock_job)

            # ControlNet parameters should be applied
            assert result["1"]["inputs"]["cfg"] == 7.5


class TestLoadWorkflowFile:
    """Test the load_workflow_file function."""

    def test_load_workflow_file_success(self):
        """Test successful workflow file loading."""
        mock_workflow = {"test": "workflow"}
        
        with patch('comfy_bridge.workflow.os.path.exists', return_value=True), \
             patch('comfy_bridge.workflow.open', create=True) as mock_open, \
             patch('comfy_bridge.workflow.json.load', return_value=mock_workflow):
            
            result = load_workflow_file("test.json")
            
            assert result == mock_workflow

    def test_load_workflow_file_not_found(self):
        """Test workflow file not found."""
        with patch('comfy_bridge.workflow.os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Workflow file not found"):
                load_workflow_file("nonexistent.json")


class TestProcessWorkflow:
    """Test the process_workflow function."""

    @pytest.mark.asyncio
    async def test_process_workflow_basic(self):
        """Test basic workflow processing."""
        workflow = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 7.5,
                },
            },
        }
        
        job = {
            "payload": {
                "prompt": "test prompt",
                "negative_prompt": "test negative",
                "seed": 98765
            },
            "params": {
                "steps": 30,
                "cfg_scale": 9.0
            }
        }

        result = await process_workflow(workflow, job)

        assert result["1"]["inputs"]["seed"] == 98765
        assert result["1"]["inputs"]["steps"] == 30
        assert result["1"]["inputs"]["cfg"] == 9.0