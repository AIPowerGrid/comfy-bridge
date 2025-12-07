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
    
    # ComfyUI model directories
    MODEL_DIRS = {
        'checkpoint': ['checkpoints', 'ckpt'],
        'vae': ['vae'],
        'text_encoder': ['text_encoders', 'clip'],
        'lora': ['loras'],
        'diffusion_models': ['diffusion_models', 'unet'],
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
    
    def find_file(self, filename: str, file_type: str = "checkpoint") -> Optional[Path]:
        """Find a model file in the appropriate directories."""
        dirs_to_check = self.MODEL_DIRS.get(file_type, ['checkpoints'])
        
        for dir_name in dirs_to_check:
            file_path = self.models_path / dir_name / filename
            if file_path.exists():
                return file_path
        
        # Fallback: search all model dirs
        for subdir in self.models_path.iterdir():
            if subdir.is_dir():
                file_path = subdir / filename
                if file_path.exists():
                    return file_path
        
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
        
        for file_info in expected_files:
            filename = file_info.get('filename') or file_info.get('file_name', '')
            file_type = file_info.get('file_type', 'checkpoint')
            
            if not filename:
                continue
            
            file_path = self.find_file(filename, file_type)
            if file_path and file_path.exists():
                present.append(f"{file_type}/{filename}")
            else:
                missing.append(f"{file_type}/{filename}")
        
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
        """
        # Check cache first
        if model_name in self._health_cache:
            return self._health_cache[model_name]
        
        # Try to get file info from blockchain client
        try:
            from comfy_bridge.modelvault_client import get_modelvault_client
            client = get_modelvault_client()
            model_info = client.find_model(model_name)
            
            if model_info and model_info.files:
                expected_files = [
                    {'filename': f.file_name, 'file_type': f.file_type}
                    for f in model_info.files
                ]
                return self.check_model_files(model_name, expected_files)
        except Exception as e:
            logger.debug(f"Could not get blockchain info for {model_name}: {e}")
        
        # Fallback: check for common checkpoint patterns
        common_patterns = [
            f"{model_name}.safetensors",
            f"{model_name}.ckpt",
            f"{model_name.lower()}.safetensors",
            f"{model_name.replace(' ', '_').lower()}.safetensors",
        ]
        
        for pattern in common_patterns:
            if self.find_file(pattern):
                return ModelHealth(
                    model_name=model_name,
                    status=ModelStatus.HEALTHY,
                    present_files=[f"checkpoint/{pattern}"],
                )
        
        return ModelHealth(
            model_name=model_name,
            status=ModelStatus.MISSING,
            error_message="Model checkpoint not found",
        )
    
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


def get_health_checker() -> ModelHealthChecker:
    """Get singleton health checker instance."""
    global _health_checker
    if _health_checker is None:
        models_path = os.environ.get("MODELS_PATH", "/app/ComfyUI/models")
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
