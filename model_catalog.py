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
MODEL_CATALOG: Dict[str, CatalogModel] = {
    **FLUX_MODELS,
}

# Name aliases for catalog lookup
CATALOG_ALIASES: Dict[str, str] = {
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
    # Direct lookup
    if name in MODEL_CATALOG:
        return MODEL_CATALOG[name]
    
    # Try alias
    canonical = CATALOG_ALIASES.get(name.lower())
    if canonical and canonical in MODEL_CATALOG:
        return MODEL_CATALOG[canonical]
    
    # Try case-insensitive
    for key in MODEL_CATALOG:
        if key.lower() == name.lower():
            return MODEL_CATALOG[key]
    
    return None


def get_all_catalog_models() -> Dict[str, CatalogModel]:
    """Get all models in the catalog."""
    return MODEL_CATALOG.copy()

