import logging
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import Settings
from ..comfyui_detect import detect_comfyui, check_comfyui_url, install_comfy_cli, install_comfyui_via_cli
from .app import app, templates, worker_state, start_worker, stop_worker

logger = logging.getLogger(__name__)

ENV_PATH = Path.cwd() / ".env"


# ---------------------------------------------------------------------------
# Middleware: redirect to setup if not configured
# ---------------------------------------------------------------------------
@app.middleware("http")
async def setup_guard(request: Request, call_next):
    path = request.url.path
    # Allow static files, API routes, and setup pages through always
    if (
        path.startswith("/static")
        or path.startswith("/api/")
        or path.startswith("/setup")
    ):
        return await call_next(request)
    # If not configured, redirect to setup
    if not worker_state["setup_complete"]:
        return RedirectResponse("/setup", status_code=303)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------
@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    detection = detect_comfyui()
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "detection": detection,
    })


@app.post("/api/setup/detect")
async def api_detect():
    """Run ComfyUI detection and return results."""
    detection = detect_comfyui()
    return {
        "found": detection.found,
        "base_path": detection.base_path,
        "url": detection.url,
        "comfy_cli_available": detection.comfy_cli_available,
        "comfy_cli_path": detection.comfy_cli_path,
        "comfy_cli_workspace": detection.comfy_cli_workspace,
        "methods": detection.methods,
    }


@app.post("/api/setup/install-comfy-cli")
async def api_install_comfy_cli():
    """Install comfy-cli via pip into the bridge's Python environment."""
    result = install_comfy_cli()
    return result


@app.post("/api/setup/check-url")
async def api_check_url(request: Request):
    """Check if a ComfyUI URL is reachable."""
    body = await request.json()
    url = body.get("url", "")
    reachable = await check_comfyui_url(url)
    return {"url": url, "reachable": reachable}


@app.post("/api/setup/install-comfyui")
async def api_install_comfyui(request: Request):
    """Install ComfyUI via comfy-cli."""
    body = await request.json()
    install_path = body.get("path")
    comfy_bin = body.get("comfy_bin")
    result = install_comfyui_via_cli(comfy_bin=comfy_bin, install_path=install_path)
    return result


@app.post("/api/setup/complete")
async def api_complete_setup(request: Request):
    """Save config and start the worker."""
    form = await request.json()

    # Build .env content, preserving any existing keys not in the form
    env_lines = _read_existing_env()
    for key, value in form.items():
        if value is not None and value != "":
            env_lines[key] = value

    # Write .env
    content = "\n".join(f"{k}={v}" for k, v in env_lines.items()) + "\n"
    ENV_PATH.write_text(content)

    # Reload settings in memory
    _reload_settings(form)

    worker_state["setup_complete"] = True

    # Start worker
    if Settings.GRID_API_KEY:
        await start_worker()

    logger.info("Setup complete. Worker starting.")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "worker_running": worker_state["running"],
        "worker_error": worker_state.get("error"),
    })


@app.get("/api/status")
async def api_status():
    return {
        "worker_running": worker_state["running"],
        "worker_error": worker_state.get("error"),
        "config": {
            "has_api_key": bool(Settings.GRID_API_KEY),
            "worker_name": Settings.GRID_WORKER_NAME,
            "comfyui_url": Settings.COMFYUI_URL,
            "models": Settings.GRID_MODELS,
            "nsfw": Settings.NSFW,
            "threads": Settings.THREADS,
            "max_pixels": Settings.MAX_PIXELS,
        },
    }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": {
            "GRID_API_KEY": Settings.GRID_API_KEY,
            "GRID_WORKER_NAME": Settings.GRID_WORKER_NAME,
            "COMFYUI_URL": Settings.COMFYUI_URL,
            "GRID_MODEL": Settings._GRID_MODELS_RAW,
            "WORKFLOW_FILE": Settings.WORKFLOW_FILE or "",
            "GRID_NSFW": str(Settings.NSFW).lower(),
            "GRID_THREADS": str(Settings.THREADS),
            "GRID_MAX_PIXELS": str(Settings.MAX_PIXELS),
            "GRID_BATCH_SIZE": str(Settings.BATCH_SIZE),
        },
    })


@app.post("/api/settings")
async def save_settings(request: Request):
    """Save settings to .env and update in-memory config."""
    form = await request.json()

    env_lines = _read_existing_env()
    for key, value in form.items():
        if value is not None and value != "":
            env_lines[key] = value
        elif key in env_lines:
            del env_lines[key]

    content = "\n".join(f"{k}={v}" for k, v in env_lines.items()) + "\n"
    ENV_PATH.write_text(content)
    _reload_settings(form)

    logger.info(f"Settings saved to {ENV_PATH}")
    return {"ok": True, "message": "Restart worker to apply all changes."}


@app.post("/api/worker/restart")
async def restart_worker():
    """Stop and restart the worker with current config."""
    await stop_worker()
    await start_worker()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_existing_env() -> dict:
    """Read existing .env into an ordered dict."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _reload_settings(form: dict):
    """Update Settings class attributes from form data."""
    if "GRID_API_KEY" in form:
        Settings.GRID_API_KEY = form["GRID_API_KEY"]
    if "GRID_WORKER_NAME" in form:
        Settings.GRID_WORKER_NAME = form["GRID_WORKER_NAME"]
    if "COMFYUI_URL" in form:
        Settings.COMFYUI_URL = form["COMFYUI_URL"]
    if "GRID_MODEL" in form:
        Settings._GRID_MODELS_RAW = form["GRID_MODEL"]
        Settings.GRID_MODELS = [
            m.strip() for m in form["GRID_MODEL"].split(",") if m.strip()
        ]
    if "GRID_NSFW" in form:
        Settings.NSFW = form["GRID_NSFW"].lower() == "true"
    if "GRID_THREADS" in form:
        Settings.THREADS = int(form["GRID_THREADS"])
    if "GRID_MAX_PIXELS" in form:
        Settings.MAX_PIXELS = int(form["GRID_MAX_PIXELS"])
    if "WORKFLOW_FILE" in form:
        Settings.WORKFLOW_FILE = form["WORKFLOW_FILE"] or None
    if "GRID_BATCH_SIZE" in form:
        Settings.BATCH_SIZE = int(form["GRID_BATCH_SIZE"])
    if "COMFYUI_BASE_PATH" in form:
        os.environ["COMFYUI_BASE_PATH"] = form["COMFYUI_BASE_PATH"]


import os  # noqa: E402
