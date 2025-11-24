"""Tests for workflow scheduler validation."""

import pytest
from comfy_bridge.workflow import map_wanvideo_scheduler, detect_workflow_model_type


class TestMapWanVideoScheduler:
    """Test the map_wanvideo_scheduler function."""

    def test_valid_scheduler_unipc(self):
        """Test that valid scheduler 'unipc' is returned as-is."""
        result = map_wanvideo_scheduler("unipc")
        assert result == "unipc"

    def test_valid_scheduler_dpm_plus_plus(self):
        """Test that valid scheduler 'dpm++' is returned as-is."""
        result = map_wanvideo_scheduler("dpm++")
        assert result == "dpm++"

    def test_valid_scheduler_dpm_plus_plus_sde(self):
        """Test that valid scheduler 'dpm++_sde' is returned as-is."""
        result = map_wanvideo_scheduler("dpm++_sde")
        assert result == "dpm++_sde"

    def test_valid_scheduler_euler(self):
        """Test that valid scheduler 'euler' is returned as-is."""
        result = map_wanvideo_scheduler("euler")
        assert result == "euler"

    def test_invalid_scheduler_dpmpp_3m_sde_gpu(self):
        """Test that invalid scheduler 'dpmpp_3m_sde_gpu' is mapped to 'dpm++_sde'."""
        result = map_wanvideo_scheduler("dpmpp_3m_sde_gpu")
        assert result == "dpm++_sde"

    def test_invalid_scheduler_dpmpp_3m_sde(self):
        """Test that invalid scheduler 'dpmpp_3m_sde' is mapped to 'dpm++_sde'."""
        result = map_wanvideo_scheduler("dpmpp_3m_sde")
        assert result == "dpm++_sde"

    def test_invalid_scheduler_dpmpp_2m(self):
        """Test that invalid scheduler 'dpmpp_2m' is mapped to 'dpm++'."""
        result = map_wanvideo_scheduler("dpmpp_2m")
        assert result == "dpm++"

    def test_invalid_scheduler_normal(self):
        """Test that invalid scheduler 'normal' is mapped to 'unipc'."""
        result = map_wanvideo_scheduler("normal")
        assert result == "unipc"

    def test_invalid_scheduler_karras(self):
        """Test that invalid scheduler 'karras' is mapped to 'unipc'."""
        result = map_wanvideo_scheduler("karras")
        assert result == "unipc"

    def test_invalid_scheduler_simple(self):
        """Test that invalid scheduler 'simple' is mapped to 'unipc'."""
        result = map_wanvideo_scheduler("simple")
        assert result == "unipc"

    def test_none_scheduler_defaults_to_unipc(self):
        """Test that None scheduler defaults to 'unipc'."""
        result = map_wanvideo_scheduler(None)
        assert result == "unipc"

    def test_empty_scheduler_defaults_to_unipc(self):
        """Test that empty string scheduler defaults to 'unipc'."""
        result = map_wanvideo_scheduler("")
        assert result == "unipc"

    def test_unknown_scheduler_defaults_to_unipc(self):
        """Test that unknown scheduler defaults to 'unipc'."""
        result = map_wanvideo_scheduler("unknown_scheduler_xyz")
        assert result == "unipc"

    def test_case_insensitive_mapping(self):
        """Test that scheduler mapping is case-insensitive."""
        result1 = map_wanvideo_scheduler("DPMPP_3M_SDE_GPU")
        result2 = map_wanvideo_scheduler("dpmpp_3m_sde_gpu")
        assert result1 == result2 == "dpm++_sde"

    def test_all_valid_schedulers(self):
        """Test all valid schedulers are returned as-is."""
        valid_schedulers = [
            'unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta',
            'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta',
            'res_multistep', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa',
            'multitalk', 'sa_ode_stable', 'rcm'
        ]
        
        for scheduler in valid_schedulers:
            result = map_wanvideo_scheduler(scheduler)
            assert result == scheduler, f"Scheduler {scheduler} should be returned as-is"


class TestDetectWorkflowModelType:
    """Test the detect_workflow_model_type function."""

    def test_detect_wanvideo_workflow(self):
        """Test detection of WanVideo workflow."""
        workflow = {
            "1": {
                "class_type": "WanVideoSampler",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "wanvideo"

    def test_detect_flux_workflow(self):
        """Test detection of Flux workflow."""
        workflow = {
            "1": {
                "class_type": "DualCLIPLoader",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "flux"

    def test_detect_sdxl_workflow(self):
        """Test detection of SDXL workflow."""
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "sdxl"

    def test_detect_unknown_workflow(self):
        """Test detection of unknown workflow."""
        workflow = {
            "1": {
                "class_type": "SomeUnknownNode",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "unknown"

    def test_detect_empty_workflow(self):
        """Test detection of empty workflow."""
        workflow = {}
        result = detect_workflow_model_type(workflow)
        assert result == "unknown"

    def test_detect_wanvideo_by_loader(self):
        """Test detection of WanVideo by WanVideoModelLoader."""
        workflow = {
            "1": {
                "class_type": "WanVideoModelLoader",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "wanvideo"

    def test_detect_wanvideo_by_decoder(self):
        """Test detection of WanVideo by WanVideoDecode."""
        workflow = {
            "1": {
                "class_type": "WanVideoDecode",
                "inputs": {}
            }
        }
        result = detect_workflow_model_type(workflow)
        assert result == "wanvideo"

