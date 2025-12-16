"""
Fallback model catalog with known download URLs.
Used when models are not registered on the blockchain or lack download URLs.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class CatalogFile:
    """A downloadable file for a model."""
    file_name: str
    file_type: str  # checkpoint, vae, text_encoder, clip, unet, etc.
    download_url: str
    target_dir: str  # Relative path within models dir (e.g., "checkpoints", "clip", "vae")
    size_bytes: int = 0
    sha256_hash: str = ""

@dataclass 
class CatalogModel:
    """Model entry in the fallback catalog."""
    name: str  # Display name / identifier
    files: List[CatalogFile]
    description: str = ""
    base_model: str = ""

# Known model download URLs - HuggingFace and other sources
try:
    WAN_MODELS: Dict[str, CatalogModel] = {
    "wan2.2_ti2v_5B": CatalogModel(
        name="wan2.2_ti2v_5B",
        description="WAN 2.2 Text-to-Image-to-Video 5B model - Image-to-video generation",
        base_model="wan2",
        files=[
            CatalogFile(
                file_name="wan2.2_ti2v_5B_fp16.safetensors",
                file_type="diffusion_models",
                target_dir="diffusion_models",
                # Try using 'raw' instead of 'resolve' - sometimes 'resolve' truncates large files
                # Also try without 'split_files' path if the file exists at root level
                download_url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors",
                size_bytes=9000000000,  # ~9GB expected size (was incorrectly set to 15GB)
                # Note: If download is only ~3GB, try alternative URL:
                # https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
                # or check if file needs to be downloaded in parts
            ),
            CatalogFile(
                file_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                file_type="text_encoders",
                target_dir="text_encoders",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                size_bytes=5157348688,
            ),
            CatalogFile(
                file_name="wan2.2_vae.safetensors",
                file_type="vae",
                target_dir="vae",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors",
                size_bytes=335304388,
            ),
        ]
    ),
    "wan2.2-t2v-a14b": CatalogModel(
        name="wan2.2-t2v-a14b",
        description="WAN 2.2 Text-to-Video 14B model - High quality text-to-video generation",
        base_model="wan2",
        files=[
            CatalogFile(
                file_name="wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                file_type="diffusion_models",
                target_dir="diffusion_models",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                size_bytes=15000000000,
            ),
            CatalogFile(
                file_name="wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                file_type="diffusion_models",
                target_dir="diffusion_models",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                size_bytes=15000000000,
            ),
            CatalogFile(
                file_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                file_type="text_encoders",
                target_dir="text_encoders",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                size_bytes=5157348688,
            ),
            CatalogFile(
                file_name="wan2.2_vae.safetensors",
                file_type="vae",
                target_dir="vae",
                download_url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors",
                size_bytes=335304388,
            ),
        ]
    ),
}
except Exception as e:
    import sys
    print(f"[ERROR] Failed to initialize WAN_MODELS: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    WAN_MODELS: Dict[str, CatalogModel] = {}

FLUX_MODELS: Dict[str, CatalogModel] = {
    "flux.1-krea-dev": CatalogModel(
        name="flux.1-krea-dev",
        description="Flux.1 Krea Dev - Creative image generation model",
        base_model="flux",
        files=[
            # FP8 UNET model
            CatalogFile(
                file_name="flux1-krea-dev_fp8_scaled.safetensors",
                file_type="unet",
                target_dir="diffusion_models",
                download_url="https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-krea-dev_fp8_scaled.safetensors",
                size_bytes=11904639672,
            ),
            # CLIP-L text encoder (goes to text_encoders folder for DualCLIPLoader)
            CatalogFile(
                file_name="clip_l.safetensors",
                file_type="clip",
                target_dir="text_encoders",
                download_url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
                size_bytes=246144152,
            ),
            # T5-XXL FP16 text encoder (REQUIRED for flux-krea - FP8 doesn't work!)
            CatalogFile(
                file_name="t5xxl_fp16.safetensors",
                file_type="text_encoder",
                target_dir="text_encoders",
                download_url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
                size_bytes=9787473824,
            ),
            # Flux VAE
            CatalogFile(
                file_name="ae.safetensors",
                file_type="vae",
                target_dir="vae",
                download_url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
                size_bytes=335304388,
            ),
        ]
    ),
    "FLUX.1-dev": CatalogModel(
        name="FLUX.1-dev",
        description="Flux.1 Dev - High quality image generation",
        base_model="flux",
        files=[
            # Full BF16 checkpoint (as UNET for UNETLoader)
            CatalogFile(
                file_name="flux1-dev.safetensors",
                file_type="unet",
                target_dir="diffusion_models",
                download_url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors",
                size_bytes=23802932552,
            ),
            # CLIP-L text encoder
            CatalogFile(
                file_name="clip_l.safetensors",
                file_type="clip",
                target_dir="clip",
                download_url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
                size_bytes=246144152,
            ),
            # T5-XXL FP8 text encoder
            CatalogFile(
                file_name="t5xxl_fp8_e4m3fn_scaled.safetensors",
                file_type="text_encoder",
                target_dir="clip",
                download_url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn_scaled.safetensors",
                size_bytes=5157348688,
            ),
            # Flux VAE
            CatalogFile(
                file_name="ae.safetensors",
                file_type="vae",
                target_dir="vae",
                download_url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
                size_bytes=335304388,
            ),
        ]
    ),
    "Chroma": CatalogModel(
        name="Chroma",
        description="Chroma model - High quality SDXL-style generation",
        base_model="sdxl",
        files=[
            CatalogFile(
                file_name="chroma-unlocked-v39.safetensors",
                file_type="checkpoint",
                target_dir="checkpoints",
                download_url="https://huggingface.co/lodestones/Chroma/resolve/main/chroma-unlocked-v39.safetensors",
                size_bytes=10178166784,
            ),
        ]
    ),
}

# Combined catalog
# Ensure dictionaries are not empty before merging
if not WAN_MODELS:
    print("[WARN] WAN_MODELS is empty!")
if not FLUX_MODELS:
    print("[WARN] FLUX_MODELS is empty!")

MODEL_CATALOG: Dict[str, CatalogModel] = {}
MODEL_CATALOG.update(WAN_MODELS)
MODEL_CATALOG.update(FLUX_MODELS)

# Debug: Verify catalog was populated
if not MODEL_CATALOG:
    print("[ERROR] MODEL_CATALOG is empty after merging!")
else:
    print(f"[DEBUG] MODEL_CATALOG initialized with {len(MODEL_CATALOG)} models")

# Name aliases for catalog lookup
CATALOG_ALIASES: Dict[str, str] = {
    # WAN model aliases
    "wan2_2_ti2v_5b": "wan2.2_ti2v_5B",
    "wan2_2_ti2v_5B": "wan2.2_ti2v_5B",
    "wan2.2-ti2v-5b": "wan2.2_ti2v_5B",
    "wan2.2-ti2v-5B": "wan2.2_ti2v_5B",
    "wan2_2_t2v_14b": "wan2.2-t2v-a14b",
    "wan2_2_t2v_14B": "wan2.2-t2v-a14b",
    "wan2.2-t2v-a14b": "wan2.2-t2v-a14b",
    "wan2.2-t2v-14b": "wan2.2-t2v-a14b",
    # FLUX model aliases
    "flux1-krea-dev": "flux.1-krea-dev",
    "flux1_krea_dev": "flux.1-krea-dev",
    "flux.1_krea_dev": "flux.1-krea-dev",
    "flux1-dev": "FLUX.1-dev",
    "flux1_dev": "FLUX.1-dev",
    "flux.1-dev": "FLUX.1-dev",
    "flux1.dev": "FLUX.1-dev",
    "chroma": "Chroma",
}


def get_catalog_model(name: str) -> Optional[CatalogModel]:
    """Get a model from the catalog by name or alias."""
    if not name:
        return None
    
    # Normalize name variations (underscores, hyphens, case)
    # Replace underscores and hyphens with dots, then collapse multiple dots
    normalized = name.replace('_', '.').replace('-', '.').lower()
    while '..' in normalized:
        normalized = normalized.replace('..', '.')
    normalized = normalized.strip('.')
    name_lower = name.lower()
    
    # Direct lookup (exact match) - try both original and stripped version
    if name in MODEL_CATALOG:
        return MODEL_CATALOG[name]
    
    # Try with stripped whitespace
    name_stripped = name.strip()
    if name_stripped != name and name_stripped in MODEL_CATALOG:
        return MODEL_CATALOG[name_stripped]
    
    # Debug: For wan2.2_ti2v_5B specifically, check if it exists
    # This helps diagnose catalog lookup issues
    if name == "wan2.2_ti2v_5B" or name_stripped == "wan2.2_ti2v_5B":
        # Check if the key exists (case-sensitive)
        if "wan2.2_ti2v_5B" in MODEL_CATALOG:
            return MODEL_CATALOG["wan2.2_ti2v_5B"]
        # Check all keys case-insensitively
        for key in MODEL_CATALOG:
            if key.lower() == "wan2.2_ti2v_5b":
                return MODEL_CATALOG[key]
    
    # Try alias lookup (case-insensitive)
    # Check exact lowercase match first
    canonical = CATALOG_ALIASES.get(name_lower)
    if canonical and canonical in MODEL_CATALOG:
        return MODEL_CATALOG[canonical]
    
    # Try normalized alias lookup (handles underscore/hyphen variations)
    canonical = CATALOG_ALIASES.get(normalized)
    if canonical and canonical in MODEL_CATALOG:
        return MODEL_CATALOG[canonical]
    
    # Try all alias keys case-insensitively (handle underscore/hyphen variations too)
    for alias_key, alias_value in CATALOG_ALIASES.items():
        alias_key_lower = alias_key.lower()
        alias_key_normalized = alias_key.replace('_', '.').replace('-', '.').lower()
        while '..' in alias_key_normalized:
            alias_key_normalized = alias_key_normalized.replace('..', '.')
        alias_key_normalized = alias_key_normalized.strip('.')
        
        # Compare normalized forms
        name_normalized_for_comparison = name_lower.replace('_', '.').replace('-', '.').lower()
        while '..' in name_normalized_for_comparison:
            name_normalized_for_comparison = name_normalized_for_comparison.replace('..', '.')
        name_normalized_for_comparison = name_normalized_for_comparison.strip('.')
        
        if (alias_key_lower == name_lower or 
            alias_key_normalized == normalized or
            alias_key_normalized == name_normalized_for_comparison):
            if alias_value in MODEL_CATALOG:
                return MODEL_CATALOG[alias_value]
    
    # Try case-insensitive direct match in catalog
    for key in MODEL_CATALOG:
        if key.lower() == name_lower:
            return MODEL_CATALOG[key]
    
    # Try normalized match (handle underscore/hyphen/dot variations)
    # This should catch wan2_2_ti2v_5B -> wan2.2_ti2v_5B
    for key in MODEL_CATALOG:
        key_normalized = key.replace('_', '.').replace('-', '.').lower()
        while '..' in key_normalized:
            key_normalized = key_normalized.replace('..', '.')
        key_normalized = key_normalized.strip('.')
        if key_normalized == normalized:
            return MODEL_CATALOG[key]
    
    # Try partial match for WAN models (wan2_2_ti2v_5B -> wan2.2_ti2v_5B)
    # This handles cases like wan2_2_ti2v_5B matching wan2.2_ti2v_5B
    if 'wan2' in normalized or 'wan' in normalized:
        for key in MODEL_CATALOG:
            if 'wan' in key.lower():
                # Normalize both for comparison
                key_normalized = key.replace('_', '.').replace('-', '.').lower()
                while '..' in key_normalized:
                    key_normalized = key_normalized.replace('..', '.')
                key_normalized = key_normalized.strip('.')
                # Check if normalized versions match (wan2.2.ti2v.5b == wan2.2.ti2v.5b)
                if key_normalized == normalized:
                    return MODEL_CATALOG[key]
                # Also try partial match - check if key parts match name parts
                key_parts = set([p for p in key_normalized.split('.') if p])
                name_parts = set([p for p in normalized.split('.') if p])
                # Match if core parts overlap (wan2, ti2v, 5b, etc.)
                common_parts = key_parts & name_parts
                if len(common_parts) >= 2 and ('wan' in common_parts or 'wan2' in common_parts):
                    return MODEL_CATALOG[key]
    
    return None


def get_all_catalog_models() -> Dict[str, CatalogModel]:
    """Get all models in the catalog."""
    return MODEL_CATALOG.copy()

