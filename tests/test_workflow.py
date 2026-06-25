import pytest
from bridge.workflow import build_workflow

# build_workflow loads a ComfyUI graph template from workflows/ for the mapped
# model. Use a model whose template is COMMITTED to the repo ("SDXL 1.0" →
# turbovision.json). (The SD1.5/Dreamshaper templates the old tests used are
# provisioned outside the repo, so those assertions were stale.) We assert graph
# invariants rather than specific node IDs, which differ per workflow template.
MODEL = "SDXL 1.0"


@pytest.mark.asyncio
async def test_build_workflow_returns_graph():
    job = {"model": MODEL, "payload": {"seed": 42, "steps": 5, "cfg_scale": 1.5}}
    wf = await build_workflow(job)
    assert isinstance(wf, dict) and wf  # non-empty ComfyUI graph
    # every value is a node spec, and at least one carries inputs
    assert all(isinstance(n, dict) for n in wf.values())
    assert any("inputs" in n for n in wf.values())


@pytest.mark.asyncio
async def test_build_workflow_minimal_fields():
    job = {"id": "x1", "model": MODEL, "payload": {}}
    wf = await build_workflow(job)
    assert isinstance(wf, dict) and wf
    assert all(isinstance(n, dict) for n in wf.values())
