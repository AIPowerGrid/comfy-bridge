import pytest
from comfy_bridge.workflow import build_workflow


def test_build_workflow_contains_nodes():
    dummy_job = {"model": "stable_diffusion_1.5", "payload": {"seed": 42, "steps": 5, "cfg_scale": 1.5}}
    wf = build_workflow(dummy_job)
    assert "3" in wf and "4" in wf
    assert wf["4"]["inputs"]["ckpt_name"]