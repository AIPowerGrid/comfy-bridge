"""Detect or install ComfyUI. Used by the setup wizard."""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    found: bool = False
    base_path: str | None = None
    url: str | None = None
    url_reachable: bool = False
    comfy_cli_available: bool = False
    comfy_cli_path: str | None = None
    comfy_cli_workspace: str | None = None
    methods: list[str] = field(default_factory=list)


def detect_comfyui() -> DetectionResult:
    """Run all detection heuristics and return a result."""
    result = DetectionResult()

    # 1. Find comfy-cli (system PATH, sibling venvs, known locations)
    comfy_bin = _find_comfy_cli()
    if comfy_bin:
        result.comfy_cli_available = True
        result.comfy_cli_path = comfy_bin
        result.methods.append(f"comfy-cli: {comfy_bin}")
        workspace = _get_comfy_cli_workspace(comfy_bin)
        if workspace:
            result.comfy_cli_workspace = workspace
            result.base_path = workspace
            result.found = True
            result.methods.append(f"comfy-cli workspace: {workspace}")

    # 2. Check env var
    env_path = os.environ.get("COMFYUI_BASE_PATH")
    if env_path and _looks_like_comfyui(env_path):
        result.base_path = env_path
        result.found = True
        result.methods.append(f"COMFYUI_BASE_PATH env: {env_path}")

    # 3. Scan common locations
    if not result.base_path:
        for candidate in _candidate_paths():
            if _looks_like_comfyui(str(candidate)):
                result.base_path = str(candidate)
                result.found = True
                result.methods.append(f"found at: {candidate}")
                break

    # 4. If we found a base_path, check for comfy-cli inside its venv
    if result.base_path and not result.comfy_cli_available:
        venv_comfy = _find_comfy_in_venv(result.base_path)
        if venv_comfy:
            result.comfy_cli_available = True
            result.comfy_cli_path = venv_comfy
            result.methods.append(f"comfy-cli in venv: {venv_comfy}")

    # 5. Derive URL default
    if result.found and not result.url:
        result.url = "http://127.0.0.1:8188"

    return result


async def check_comfyui_url(url: str) -> bool:
    """Ping the ComfyUI API to see if it's reachable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{url.rstrip('/')}/system_stats")
            return resp.status_code == 200
    except Exception:
        return False


def install_comfy_cli() -> dict:
    """Install comfy-cli into the current Python environment."""
    python = sys.executable
    try:
        proc = subprocess.run(
            [python, "-m", "pip", "install", "comfy-cli"],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0:
            # Verify it's now findable
            comfy_bin = shutil.which("comfy")
            if not comfy_bin:
                # Check in the same bin dir as our python
                bin_dir = Path(python).parent
                candidate = bin_dir / "comfy"
                if candidate.exists():
                    comfy_bin = str(candidate)
            return {
                "ok": True,
                "comfy_path": comfy_bin,
                "output": proc.stdout[-500:] if len(proc.stdout) > 500 else proc.stdout,
            }
        else:
            return {"ok": False, "error": proc.stderr or proc.stdout}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pip install timed out (2 min)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def install_comfyui_via_cli(comfy_bin: str | None = None, install_path: str | None = None) -> dict:
    """Run comfy-cli to install ComfyUI. Returns status dict."""
    comfy = comfy_bin or _find_comfy_cli()
    if not comfy:
        return {"ok": False, "error": "comfy-cli not found. Install it first."}

    cmd = [comfy, "install", "--skip-prompt"]
    if install_path:
        cmd.extend(["--path", install_path])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode == 0:
            return {
                "ok": True,
                "output": proc.stdout[-1000:] if len(proc.stdout) > 1000 else proc.stdout,
            }
        else:
            return {"ok": False, "error": proc.stderr or proc.stdout}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Installation timed out (10 min)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_comfy_cli() -> str | None:
    """Find the comfy binary — system PATH, our venv, or sibling venvs."""
    # System PATH
    found = shutil.which("comfy")
    if found:
        return found

    # Same bin dir as the running Python (e.g. bridge's own venv)
    bin_dir = Path(sys.executable).parent
    for name in ["comfy", "comfy.exe"]:
        candidate = bin_dir / name
        if candidate.exists():
            return str(candidate)

    # Check sibling/parent venvs (e.g. ../venv/bin/comfy for ComfyUI next door)
    cwd = Path.cwd()
    for venv_root in [cwd.parent, cwd.parent / "ComfyUI", Path.home() / "ComfyUI"]:
        c = _find_comfy_in_venv(str(venv_root))
        if c:
            return c

    return None


def _find_comfy_in_venv(base: str) -> str | None:
    """Check if comfy-cli exists in a venv under the given path."""
    p = Path(base)
    for bin_path in [p / "venv" / "bin" / "comfy", p / "venv" / "Scripts" / "comfy.exe"]:
        if bin_path.exists():
            return str(bin_path)
    return None


def _get_comfy_cli_workspace(comfy_bin: str) -> str | None:
    """Try to get the ComfyUI workspace path from comfy-cli."""
    # Try reading comfy-cli config files
    import json
    config_paths = [
        Path.home() / ".config" / "comfy-cli" / "config.json",
        Path.home() / ".comfy" / "config.json",
    ]
    for cfg_path in config_paths:
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
                workspace = data.get("workspace") or data.get("default_workspace")
                if workspace and Path(workspace).is_dir():
                    return str(workspace)
            except Exception:
                pass

    # Fallback: run `comfy env` and parse output
    try:
        proc = subprocess.run(
            [comfy_bin, "env"],
            capture_output=True, text=True, timeout=10,
        )
        for line in proc.stdout.splitlines():
            if "workspace" in line.lower() or "comfyui" in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    candidate = parts[1].strip()
                    if Path(candidate).is_dir():
                        return candidate
    except Exception:
        pass

    return None


def _looks_like_comfyui(path: str) -> bool:
    """Heuristic: does this directory look like a ComfyUI install?"""
    p = Path(path)
    if not p.is_dir():
        return False
    has_models = (p / "models").is_dir()
    if not has_models:
        return False
    # Classic install: main.py or server.py at root
    has_entry = (p / "main.py").exists() or (p / "server.py").exists()
    # comfy-cli managed: custom_nodes/ + models/
    has_custom_nodes = (p / "custom_nodes").is_dir()
    # comfy in the venv
    has_venv_comfy = bool(_find_comfy_in_venv(path))
    return has_entry or has_custom_nodes or has_venv_comfy


def _candidate_paths() -> list[Path]:
    """Common places where ComfyUI might be installed."""
    home = Path.home()
    cwd = Path.cwd()
    candidates = [
        cwd.parent,                # sibling of bridge install
        cwd.parent / "ComfyUI",
        home / "ComfyUI",
        home / "comfyui",
    ]
    # Platform-specific
    if sys.platform == "win32":
        candidates.extend([
            Path("C:/ComfyUI"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "ComfyUI",
        ])
    else:
        candidates.append(Path("/opt/ComfyUI"))
    # Parent directories up to 3 levels
    p = cwd
    for _ in range(3):
        p = p.parent
        candidates.append(p / "ComfyUI")
        if _looks_like_comfyui(str(p)):
            candidates.insert(0, p)
    return candidates
