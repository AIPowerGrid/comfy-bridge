import pytest
import respx
import httpx
from comfy_bridge.api_client import APIClient


@respx.mock
@pytest.mark.asyncio
async def test_pop_job_success():
    route = respx.post("https://api.aipowergrid.io/api/v2/generate/pop").mock(
        return_value=httpx.Response(200, json={"id": "job1", "model": "m"})
    )
    client = APIClient()
    job = await client.pop_job()
    assert job["id"] == "job1"
    assert route.called