"""
Optional Dependencies Manager

This module handles optional dependencies that may not be available
in all environments, providing graceful fallbacks and clear messaging.
"""

import logging
import importlib.util

logger = logging.getLogger(__name__)

class OptionalDependency:
    """Represents an optional dependency with fallback behavior"""

    def __init__(self, name: str, pip_name: str = None, description: str = "", auto_install: bool = False):
        self.name = name
        self.pip_name = pip_name or name
        self.description = description or f"Optional package: {name}"
        self.auto_install = auto_install
        self._available = None

    def is_available(self) -> bool:
        """Check if the dependency is available"""
        if self._available is None:
            try:
                importlib.import_module(self.name)
                self._available = True
                logger.debug(f"✅ {self.name} is available")
            except ImportError:
                self._available = False
                logger.debug(f"⚠️  {self.name} is not available")
        return self._available

    def try_import(self, fallback=None):
        """Try to import the module, return fallback if not available"""
        if self.is_available():
            try:
                return importlib.import_module(self.name)
            except ImportError:
                pass
        return fallback

# Define optional dependencies
OPTIONAL_DEPS = {
    'sageattention': OptionalDependency(
        'sageattention',
        description="High-performance attention optimization for better inference speed"
    ),
    'onnx': OptionalDependency(
        'onnx',
        description="Open Neural Network Exchange for model serialization"
    ),
    'onnxruntime': OptionalDependency(
        'onnxruntime',
        description="ONNX Runtime for optimized model execution"
    ),
    'flash_attn': OptionalDependency(
        'flash_attn',
        pip_name='flash-attn',
        description="Flash Attention for memory-efficient attention computation"
    ),
}

def check_optional_dependencies():
    """Check all optional dependencies and log their status"""
    logger.info("🔍 Checking optional dependencies...")

    available_count = 0
    total_count = len(OPTIONAL_DEPS)

    for name, dep in OPTIONAL_DEPS.items():
        if dep.is_available():
            available_count += 1
            logger.info(f"  ✅ {name}: Available")
        else:
            logger.info(f"  ⚠️  {name}: Not available - {dep.description}")

    logger.info(f"📊 Optional dependencies: {available_count}/{total_count} available")

    if available_count < total_count:
        logger.info("💡 To improve performance, consider installing missing optional dependencies:")
        for name, dep in OPTIONAL_DEPS.items():
            if not dep.is_available():
                logger.info(f"   pip install {dep.pip_name}")

    return available_count, total_count

def get_available_modules():
    """Get a dict of available optional modules"""
    return {name: dep.is_available() for name, dep in OPTIONAL_DEPS.items()}

# Initialize on module load
_available_deps = None

def init_optional_deps():
    """Initialize optional dependencies check (called once)"""
    global _available_deps
    if _available_deps is None:
        _available_deps = get_available_modules()
    return _available_deps

# Export convenience functions
def has_sageattention():
    """Check if sageattention is available"""
    return OPTIONAL_DEPS['sageattention'].is_available()

def has_onnx():
    """Check if ONNX is available"""
    return OPTIONAL_DEPS['onnx'].is_available()

def has_flash_attention():
    """Check if flash attention is available"""
    return OPTIONAL_DEPS['flash_attn'].is_available() or OPTIONAL_DEPS['onnxruntime'].is_available()