"""
Health Check and Model Validation for ComfyUI Bridge.

This module provides:
- Model file validation (check all required files exist)
- Job pre-validation (reject jobs for incomplete models)
- Health status reporting
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

# Ensure .env is loaded before reading environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    HEALTHY = "healthy"           # All files present, ready to serve
    INCOMPLETE = "incomplete"     # Some files missing
    MISSING = "missing"           # Model not downloaded
    ERROR = "error"               # Error checking status


@dataclass
class ModelHealth:
    """Health status for a single model."""
    model_name: str
    status: ModelStatus
    missing_files: List[str] = field(default_factory=list)
    present_files: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        return self.status == ModelStatus.HEALTHY
    
    @property
    def can_serve(self) -> bool:
        """Check if model can serve jobs (has at least checkpoint)."""
        return self.status in (ModelStatus.HEALTHY, ModelStatus.INCOMPLETE) and \
               any('checkpoint' in f or 'diffusion' in f for f in self.present_files)


@dataclass
class WorkerHealth:
    """Overall health status for the worker."""
    healthy_models: List[str] = field(default_factory=list)
    incomplete_models: List[str] = field(default_factory=list)
    missing_models: List[str] = field(default_factory=list)
    error_models: List[str] = field(default_factory=list)
    model_details: Dict[str, ModelHealth] = field(default_factory=dict)
    
    @property
    def total_models(self) -> int:
        return len(self.healthy_models) + len(self.incomplete_models) + \
               len(self.missing_models) + len(self.error_models)
    
    @property
    def servable_models(self) -> List[str]:
        """Models that can accept jobs."""
        return self.healthy_models + [
            m for m in self.incomplete_models 
            if self.model_details.get(m, ModelHealth(m, ModelStatus.ERROR)).can_serve
        ]
    
    def to_dict(self) -> dict:
        return {
            "healthy": len(self.healthy_models),
            "incomplete": len(self.incomplete_models),
            "missing": len(self.missing_models),
            "error": len(self.error_models),
            "total": self.total_models,
            "servable": len(self.servable_models),
            "healthy_models": self.healthy_models,
            "incomplete_models": self.incomplete_models,
            "servable_models": self.servable_models,
        }


class ModelHealthChecker:
    """
    Validates model files and tracks health status.
    
    Integrates with blockchain registry to know expected files.
    """
    
    # All known model directories to search
    ALL_MODEL_DIRS = [
        'checkpoints', 'ckpt', 'vae', 'clip', 'text_encoders', 
        'loras', 'diffusion_models', 'unet', 'embeddings', 'controlnet'
    ]
    
    # ComfyUI model directories - search multiple possible locations by type
    MODEL_DIRS = {
        'checkpoint': ['checkpoints', 'ckpt', 'diffusion_models', 'unet'],
        'checkpoints': ['checkpoints', 'ckpt', 'diffusion_models', 'unet'],
        'vae': ['vae'],
        'text_encoder': ['text_encoders', 'clip', 'checkpoints'],
        'text_encoders': ['text_encoders', 'clip', 'checkpoints'],
        'clip': ['clip', 'text_encoders', 'checkpoints'],
        'lora': ['loras'],
        'loras': ['loras'],
        'diffusion_models': ['diffusion_models', 'unet'],
        'unet': ['unet', 'diffusion_models'],
    }
    
    def __init__(self, models_path: str = "/app/ComfyUI/models"):
        self.models_path = Path(models_path)
        self._health_cache: Dict[str, ModelHealth] = {}
        self._advertised_models: Set[str] = set()
    
    def set_advertised_models(self, models: List[str]):
        """Set which models the worker is advertising."""
        self._advertised_models = set(models)
        # Clear cache when model list changes
        self._health_cache.clear()
    
    def list_all_model_files(self) -> Dict[str, List[str]]:
        """
        List all model files found in the models directory.
        
        Returns:
            Dict mapping directory name to list of files found
        """
        result = {}
        if not self.models_path.exists():
            logger.warning(f"Models path does not exist: {self.models_path}")
            return result
        
        try:
            for subdir in self.models_path.iterdir():
                if subdir.is_dir():
                    files = []
                    # Walk this subdirectory recursively
                    for root, dirs, filenames in os.walk(subdir):
                        for f in filenames:
                            if f.endswith(('.safetensors', '.ckpt', '.pt', '.pth', '.bin')):
                                # Get relative path from the subdir
                                rel_path = os.path.relpath(os.path.join(root, f), subdir)
                                files.append(rel_path)
                    if files:
                        result[subdir.name] = sorted(files)
        except PermissionError as e:
            logger.warning(f"Permission error listing model files: {e}")
        
        return result
    
    def file_exists(self, filename: str) -> bool:
        """Check if a model file exists anywhere in the models directory."""
        return self.find_file(filename) is not None
    
    def find_file(self, filename: str, file_type: str = "checkpoint") -> Optional[Path]:
        """Find a model file in the appropriate directories."""
        dirs_to_check = self.MODEL_DIRS.get(file_type, ['checkpoints'])
        
        logger.debug(f"Looking for file '{filename}' (type={file_type}) in {self.models_path}")
        
        # First check the type-specific directories
        for dir_name in dirs_to_check:
            file_path = self.models_path / dir_name / filename
            logger.debug(f"  Checking type-specific: {file_path}")
            if file_path.exists():
                logger.debug(f"  ✓ Found at {file_path}")
                return file_path
        
        # Fallback: search all immediate subdirs
        if self.models_path.exists():
            try:
                for subdir in self.models_path.iterdir():
                    if subdir.is_dir():
                        file_path = subdir / filename
                        if file_path.exists():
                            logger.debug(f"  ✓ Found in immediate subdir: {file_path}")
                            return file_path
                        # Case-insensitive check
                        for f in subdir.iterdir():
                            if f.is_file() and f.name.lower() == filename.lower():
                                logger.debug(f"  ✓ Found (case-insensitive) in subdir: {f}")
                                return f
            except PermissionError as e:
                logger.warning(f"  Permission error scanning subdirs: {e}")
        
        # Deep search: walk entire tree (handles nested subdirs like diffusion_models/wan/)
        if self.models_path.exists():
            try:
                for root, dirs, files in os.walk(self.models_path):
                    # Exact match
                    if filename in files:
                        result = Path(root) / filename
                        logger.debug(f"  ✓ Found in deep search: {result}")
                        return result
                    # Case-insensitive fallback
                    for f in files:
                        if f.lower() == filename.lower():
                            result = Path(root) / f
                            logger.debug(f"  ✓ Found (case-insensitive) in deep search: {result}")
                            return result
            except PermissionError as e:
                logger.warning(f"  Permission error in deep search: {e}")
        
        logger.debug(f"  ✗ File not found: {filename}")
        return None
    
    def check_model_files(
        self, 
        model_name: str, 
        expected_files: List[Dict[str, str]]
    ) -> ModelHealth:
        """
        Check if all expected files for a model are present.
        
        Args:
            model_name: Display name of the model
            expected_files: List of {filename, file_type} dicts
            
        Returns:
            ModelHealth with status and file lists
        """
        missing = []
        present = []
        
        logger.debug(f"Checking {len(expected_files)} files for model {model_name} in {self.models_path}")
        
        for file_info in expected_files:
            filename = file_info.get('filename') or file_info.get('file_name', '')
            file_type = file_info.get('file_type', 'checkpoint')
            
            if not filename:
                continue
            
            file_path = self.find_file(filename, file_type)
            if file_path and file_path.exists():
                present.append(f"{file_type}/{filename}")
                logger.debug(f"  ✓ Found {filename} at {file_path}")
            else:
                missing.append(f"{file_type}/{filename}")
                logger.debug(f"  ✗ Missing {filename} (type={file_type})")
        
        if not expected_files:
            # No file info available
            status = ModelStatus.ERROR
            error_msg = "No file information available for model"
        elif not missing:
            status = ModelStatus.HEALTHY
            error_msg = None
        elif not present:
            status = ModelStatus.MISSING
            error_msg = f"All {len(missing)} files missing"
        else:
            status = ModelStatus.INCOMPLETE
            error_msg = f"{len(missing)} of {len(expected_files)} files missing"
        
        health = ModelHealth(
            model_name=model_name,
            status=status,
            missing_files=missing,
            present_files=present,
            error_message=error_msg,
        )
        
        self._health_cache[model_name] = health
        return health
    
    def check_model_by_name(self, model_name: str) -> ModelHealth:
        """
        Check model health using blockchain registry.
        
        Falls back to simple file existence check if no blockchain data.
        For model name variants (aliases), inherits health from canonical name.
        """
        # Check cache first
        if model_name in self._health_cache:
            return self._health_cache[model_name]
        
        # Try to get file info from blockchain client
        try:
            from comfy_bridge.modelvault_client import get_modelvault_client, MODEL_NAME_ALIASES
            client = get_modelvault_client()
            model_info = client.find_model(model_name)
            
            if model_info and model_info.files:
                expected_files = [
                    {'filename': f.file_name, 'file_type': f.file_type}
                    for f in model_info.files
                ]
                health = self.check_model_files(model_name, expected_files)
                
                # If this is an alias and the canonical model is healthy, inherit that status
                canonical_name = MODEL_NAME_ALIASES.get(model_name.lower())
                if canonical_name and canonical_name != model_name:
                    # Check if we already validated the canonical name
                    if canonical_name in self._health_cache:
                        canonical_health = self._health_cache[canonical_name]
                        if canonical_health.is_healthy or canonical_health.can_serve:
                            # Inherit healthy status from canonical model
                            health = ModelHealth(
                                model_name=model_name,
                                status=canonical_health.status,
                                missing_files=canonical_health.missing_files,
                                present_files=canonical_health.present_files,
                            )
                
                self._health_cache[model_name] = health
                return health
            elif model_info:
                # Model found in registry but no files info - assume it's valid if workflow exists
                logger.debug(f"Model {model_name} found in registry without file info, marking as healthy")
                health = ModelHealth(
                    model_name=model_name,
                    status=ModelStatus.HEALTHY,
                    present_files=["registry/validated"],
                )
                self._health_cache[model_name] = health
                return health
        except Exception as e:
            logger.debug(f"Could not get blockchain info for {model_name}: {e}")
        
        # Check if this is a known alias - if so, check canonical name first
        try:
            from comfy_bridge.modelvault_client import MODEL_NAME_ALIASES
            canonical_name = MODEL_NAME_ALIASES.get(model_name.lower())
            if canonical_name and canonical_name != model_name:
                # Recursively check canonical name
                canonical_health = self.check_model_by_name(canonical_name)
                if canonical_health.is_healthy or canonical_health.can_serve:
                    # Alias inherits health from canonical model
                    health = ModelHealth(
                        model_name=model_name,
                        status=canonical_health.status,
                        missing_files=canonical_health.missing_files,
                        present_files=canonical_health.present_files,
                    )
                    self._health_cache[model_name] = health
                    return health
        except Exception as e:
            logger.debug(f"Could not check alias for {model_name}: {e}")
        
        # Fallback: check for common checkpoint patterns
        common_patterns = [
            f"{model_name}.safetensors",
            f"{model_name}.ckpt",
            f"{model_name.lower()}.safetensors",
            f"{model_name.replace(' ', '_').lower()}.safetensors",
            # Also check normalized patterns (dots/hyphens -> underscores)
            f"{model_name.replace('.', '_').replace('-', '_').lower()}.safetensors",
        ]
        
        for pattern in common_patterns:
            if self.find_file(pattern):
                health = ModelHealth(
                    model_name=model_name,
                    status=ModelStatus.HEALTHY,
                    present_files=[f"checkpoint/{pattern}"],
                )
                self._health_cache[model_name] = health
                return health
        
        # Check if this model has a valid workflow (trust workflow validation)
        try:
            from comfy_bridge.model_mapper import get_workflow_validated_models
            workflow_validated = get_workflow_validated_models()
            if model_name in workflow_validated:
                logger.debug(f"Model {model_name} has valid workflow, marking as healthy")
                health = ModelHealth(
                    model_name=model_name,
                    status=ModelStatus.HEALTHY,
                    present_files=["workflow/validated"],
                )
                self._health_cache[model_name] = health
                return health
        except Exception as e:
            logger.debug(f"Could not check workflow validation for {model_name}: {e}")
        
        health = ModelHealth(
            model_name=model_name,
            status=ModelStatus.MISSING,
            error_message="Model checkpoint not found",
        )
        self._health_cache[model_name] = health
        return health
    
    def get_worker_health(self) -> WorkerHealth:
        """Get overall health status for all advertised models."""
        health = WorkerHealth()
        
        for model_name in self._advertised_models:
            model_health = self.check_model_by_name(model_name)
            health.model_details[model_name] = model_health
            
            if model_health.status == ModelStatus.HEALTHY:
                health.healthy_models.append(model_name)
            elif model_health.status == ModelStatus.INCOMPLETE:
                health.incomplete_models.append(model_name)
            elif model_health.status == ModelStatus.MISSING:
                health.missing_models.append(model_name)
            else:
                health.error_models.append(model_name)
        
        return health
    
    def can_serve_model(self, model_name: str) -> tuple[bool, str]:
        """
        Check if a model can serve jobs.
        
        Returns:
            (can_serve, reason)
        """
        health = self.check_model_by_name(model_name)
        
        if health.is_healthy:
            return True, "Model ready"
        
        if health.can_serve:
            return True, f"Model partially ready ({len(health.missing_files)} optional files missing)"
        
        if health.status == ModelStatus.MISSING:
            return False, "Model not downloaded"
        
        if health.status == ModelStatus.INCOMPLETE:
            return False, f"Critical files missing: {', '.join(health.missing_files[:3])}"
        
        return False, health.error_message or "Unknown error"
    
    def validate_job(self, model_name: str) -> tuple[bool, str]:
        """
        Validate if a job can be accepted for a model.
        
        Call this before accepting a job from the grid.
        
        Returns:
            (accept_job, reason)
        """
        can_serve, reason = self.can_serve_model(model_name)
        
        if not can_serve:
            logger.warning(f"Rejecting job for {model_name}: {reason}")
        
        return can_serve, reason
    
    def refresh(self):
        """Clear health cache and recheck all models."""
        self._health_cache.clear()


# Global singleton
_health_checker: Optional[ModelHealthChecker] = None


def _find_models_path() -> str:
    """Find the actual models directory, checking multiple possible locations."""
    # Check env var first
    env_path = os.environ.get("MODELS_PATH")
    logger.info(f"MODELS_PATH env var: '{env_path}'")
    
    if env_path:
        # Normalize path (handle forward slashes on Windows)
        normalized = Path(env_path).resolve()
        logger.info(f"MODELS_PATH normalized: '{normalized}'")
        if normalized.is_dir():
            logger.info(f"✓ Using MODELS_PATH from env: {normalized}")
            return str(normalized)
        else:
            logger.warning(f"✗ MODELS_PATH exists but is not a directory or doesn't exist: {normalized}")
    
    # Check common Docker/Linux paths
    for path in ["/app/ComfyUI/models", "/persistent_volumes/models"]:
        if os.path.isdir(path):
            logger.info(f"Found models at Docker path: {path}")
            return path
    
    # Check paths relative to the comfy_bridge package (for local development)
    this_dir = Path(__file__).parent.absolute()
    comfy_bridge_root = this_dir.parent  # c:\dev\comfy-bridge
    
    # Check for persistent_volumes/models relative to project root
    relative_paths = [
        comfy_bridge_root / "persistent_volumes" / "models",
        comfy_bridge_root.parent / "persistent_volumes" / "models",  # one level up
        comfy_bridge_root / "models",
        Path.home() / "ComfyUI" / "models",  # User's home directory
    ]
    
    for path in relative_paths:
        logger.debug(f"Checking relative path: {path}")
        if path.is_dir():
            logger.info(f"Found models at relative path: {path}")
            return str(path)
    
    # Fall back to default
    logger.warning("Could not find models directory, using default /app/ComfyUI/models")
    return "/app/ComfyUI/models"


def get_health_checker() -> ModelHealthChecker:
    """Get singleton health checker instance."""
    global _health_checker
    if _health_checker is None:
        models_path = _find_models_path()
        logger.info(f"Health checker using models path: {models_path}")
        # Verify the path exists and list subdirs for debugging
        p = Path(models_path)
        if p.exists():
            subdirs = [d.name for d in p.iterdir() if d.is_dir()]
            logger.info(f"  Models path exists, subdirs: {subdirs[:10]}...")
        else:
            logger.warning(f"  Models path does NOT exist: {models_path}")
        _health_checker = ModelHealthChecker(models_path)
    return _health_checker


def validate_job_for_model(model_name: str) -> tuple[bool, str]:
    """
    Convenience function to validate a job.
    
    Usage:
        can_accept, reason = validate_job_for_model("FLUX.1-dev")
        if not can_accept:
            return reject_job(reason)
    """
    checker = get_health_checker()
    return checker.validate_job(model_name)


def get_worker_health_status() -> dict:
    """Get worker health as a dictionary for API responses."""
    checker = get_health_checker()
    return checker.get_worker_health().to_dict()
