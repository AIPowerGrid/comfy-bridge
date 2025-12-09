"""
WAN Video Model Asset Management

Handles symlink creation and integrity checking for WAN video model assets.
Model information is sourced from the blockchain (ModelVault contract).
"""

import logging
import os
import json
import struct
from typing import Dict, Optional, Tuple

try:
    from . import download_models_from_catalog as downloader
except Exception:  # pragma: no cover - optional fallback when module unavailable
    downloader = None

logger = logging.getLogger(__name__)

# Filename -> destination relative to models root
WAN_SYMLINK_TARGETS: Dict[str, Tuple[str, ...]] = {
    "umt5_xxl_fp8_e4m3fn_scaled.safetensors": ("clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors",),
    "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors": ("unet/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",),
    "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors": ("unet/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",),
    "wan2.2_ti2v_5B_fp16.safetensors": ("unet/wan2.2_ti2v_5B_fp16.safetensors",),
    "wan2.2_vae.safetensors": ("vae/wan2.2_vae.safetensors",),
    "wan_2.1_vae.safetensors": ("vae/wan_2.1_vae.safetensors",),
}

WAN_ASSET_MODEL_MAP: Dict[str, str] = {
    "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors": "wan2.2-t2v-a14b",
    "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors": "wan2.2-t2v-a14b",
    "wan2.2_ti2v_5B_fp16.safetensors": "wan2.2_ti2v_5B",
}

# Check both possible model locations
DEFAULT_MODELS_PATHS = [
    "/app/ComfyUI/models",
    "/persistent_volumes/models",
]
DEFAULT_MODELS_PATH = "/app/ComfyUI/models"


def _find_wan_asset(filename: str, models_root: str) -> Optional[str]:
    """Search common folders (and fallback to walking the tree) for a Wan asset."""
    # Primary directories to check
    candidate_dirs = [
        "diffusion_models",  # New ComfyUI location
        "diffusion_models/wan",  # Possible subdirectory
        "unet",
        "unet/wan",
        "checkpoints",
        "clip",
        "text_encoders",
        "vae",
        "loras",
    ]

    for sub in candidate_dirs:
        candidate = os.path.join(models_root, sub, filename)
        if os.path.exists(candidate):
            return candidate

    # Deep search: walk the entire tree to find the file
    for root, dirs, files in os.walk(models_root):
        if filename in files:
            return os.path.join(root, filename)
        # Also check case-insensitive match
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root, f)

    return None


def _expected_safetensors_size(path: str) -> Tuple[bool, Optional[int]]:
    try:
        with open(path, "rb") as f:
            header_size_raw = f.read(8)
            if len(header_size_raw) != 8:
                return False, None
            header_size = struct.unpack("<Q", header_size_raw)[0]
            header_bytes = f.read(header_size)
            if len(header_bytes) != header_size:
                return False, None
            header = json.loads(header_bytes)
        max_offset = 0
        for tensor_meta in header.values():
            if isinstance(tensor_meta, dict):
                offsets = tensor_meta.get("data_offsets")
                if isinstance(offsets, list) and len(offsets) == 2:
                    max_offset = max(max_offset, int(offsets[1]))
        required_size = 8 + header_size + max_offset
        actual_size = os.path.getsize(path)
        if max_offset == 0:
            return True, required_size
        return actual_size >= required_size, required_size
    except Exception as exc:
        logger.warning("Failed to inspect safetensors header for %s: %s", path, exc)
        return False, None


def _is_file_complete(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if path.endswith(".safetensors"):
        ok, required = _expected_safetensors_size(path)
        if not ok:
            logger.warning(
                "Detected incomplete safetensors file: %s (expected ≥ %s bytes)",
                path,
                required or "unknown",
            )
            return False
    return True


def _redownload_asset(filename: str, models_root: str) -> bool:
    """
    Attempt to re-download a corrupted WAN asset.
    
    Model information is fetched from the blockchain registry.
    """
    model_id = WAN_ASSET_MODEL_MAP.get(filename)
    if not model_id or downloader is None:
        return False
    
    logger.warning(
        "Attempting to re-download Wan asset %s (model %s) due to integrity failure",
        filename,
        model_id,
    )
    
    try:
        # Download using model_id - downloader will resolve from chain/fallback sources
        return downloader.download_models(
            [model_id],
            models_root,
            resolve_deps=True,
        )
    except Exception as exc:
        logger.error("Failed to re-download %s: %s", filename, exc)
        return False


def _ensure_symlink(source: str, destination: str) -> bool:
    """Ensure destination is a symlink pointing to the source."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    if os.path.islink(destination):
        current_target = os.path.realpath(destination)
        if current_target == os.path.realpath(source):
            logger.debug("Symlink already correct: %s -> %s", destination, source)
            return True
        os.unlink(destination)
        logger.debug("Removed stale symlink: %s", destination)
    elif os.path.exists(destination):
        logger.info(
            "Destination already exists and is not a symlink: %s (skipping)",
            destination,
        )
        return False

    os.symlink(source, destination)
    logger.info("Linked Wan asset: %s -> %s", destination, source)
    return True


def _find_models_root() -> str:
    """Find the actual models directory, checking multiple possible locations."""
    # Check env var first
    env_path = os.environ.get("MODELS_PATH")
    if env_path and os.path.isdir(env_path):
        return os.path.abspath(env_path)
    
    # Check default paths
    for path in DEFAULT_MODELS_PATHS:
        if os.path.isdir(path):
            return os.path.abspath(path)
    
    # Fall back to default
    return os.path.abspath(DEFAULT_MODELS_PATH)


def ensure_wan_symlinks(models_root: Optional[str] = None) -> None:
    """Make sure Wan model components live where vanilla ComfyUI expects them."""
    root = models_root or _find_models_root()
    root = os.path.abspath(root)

    if not os.path.isdir(root):
        logger.warning("Models directory does not exist yet: %s", root)
        return

    created_any = False
    for filename, destinations in WAN_SYMLINK_TARGETS.items():
        source = _find_wan_asset(filename, root)
        if not source:
            logger.warning("Wan asset missing: %s (searched under %s)", filename, root)
            continue

        if not _is_file_complete(source):
            logger.warning("Wan asset appears truncated: %s", source)
            try:
                os.unlink(source)
            except OSError as exc:
                logger.error("Failed to remove corrupted asset %s: %s", source, exc)
                continue
            if not _redownload_asset(filename, root):
                logger.error(
                    "Re-download failed for %s. Please rerun download_models.",
                    filename,
                )
                continue
            source = _find_wan_asset(filename, root)
            if not source or not _is_file_complete(source):
                logger.error(
                    "Asset %s remains unavailable after re-download attempt", filename
                )
                continue

        for dest_rel in destinations:
            destination = os.path.join(root, dest_rel)
            try:
                if _ensure_symlink(source, destination):
                    created_any = True
            except OSError as exc:
                logger.warning("Failed to link %s -> %s: %s", destination, source, exc)

    if not created_any:
        logger.debug("Wan symlink check completed - no changes were necessary.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ensure_wan_symlinks()

