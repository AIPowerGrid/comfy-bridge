import pytest
import respx
import httpx
import os
from bridge.api_client import APIClient
from bridge.config import Settings

from dotenv import load_dotenv

load_dotenv()


@respx.mock
@pytest.mark.asyncio
async def test_pop_job_success():
    route = respx.post(f"{Settings.GRID_API_URL}/v2/generate/pop").mock(
        return_value=httpx.Response(200, json={"id": "job1", "model": "m"})
    )
    client = APIClient()
    job = await client.pop_job()
    assert job["id"] == "job1"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_pop_job_success_with_models_arg(monkeypatch):
    # GIVEN a mocked 200 response for pop_job
    route = respx.post(f"{Settings.GRID_API_URL}/v2/generate/pop").mock(
        return_value=httpx.Response(200, json={"id": "job1", "model": "m1"})
    )
    client = APIClient()
    # WHEN pop_job is called with an explicit models list
    job = await client.pop_job(models=["m1", "m2"])
    # THEN it returns the JSON and uses our route
    assert job["id"] == "job1"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_pop_job_success_default_models(monkeypatch):
    # GIVEN Settings.GRID_MODELS is set to ["foo"]
    monkeypatch.setattr(Settings, "GRID_MODELS", ["foo"])
    route = respx.post(f"{Settings.GRID_API_URL}/v2/generate/pop").mock(
        return_value=httpx.Response(200, json={"id": "job2", "model": "foo"})
    )
    client = APIClient()
    # WHEN pop_job() is called without args
    job = await client.pop_job()
    # THEN it falls back to Settings.GRID_MODELS
    assert job["id"] == "job2"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_pop_job_raises_on_http_error():
    # GIVEN a 400 response
    respx.post(f"{Settings.GRID_API_URL}/v2/generate/pop").mock(
        return_value=httpx.Response(400, json={"message": "bad"})
    )
    client = APIClient()
    # WHEN pop_job is called
    with pytest.raises(httpx.HTTPStatusError):
        await client.pop_job(models=["x"])
