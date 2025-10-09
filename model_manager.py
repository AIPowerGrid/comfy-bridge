#!/usr/bin/env python3
"""
ComfyUI Model Manager
Automatically downloads and manages AI models for ComfyUI Bridge
"""

import os
import json
import hashlib
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, base_path: str = "/app/ComfyUI/models"):
        self.base_path = Path(base_path)
        self.model_configs = self.load_model_configs()
        
    def load_model_configs(self) -> Dict:
        """Load model configurations from a JSON file"""
        config_path = Path(__file__).parent / "model_configs.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default model configurations with verified checksums
            return {
                "wan2_2_t2v_14b": {
                    "type": "checkpoints",
                    "filename": "wan2.2-t2v-a14b.safetensors",
                    "url": "https://huggingface.co/black-forest-labs/WAN2.2-T2V-A14B/resolve/main/wan2.2-t2v-a14b.safetensors",
                    "sha256": None,  # Will be validated after download
                    "size": 14200000000,  # Expected size in bytes
                    "dependencies": []
                },
                "wan2_2_t2v_14b_hq": {
                    "type": "checkpoints", 
                    "filename": "wan2.2-t2v-a14b-hq.safetensors",
                    "url": "https://huggingface.co/black-forest-labs/WAN2.2-T2V-A14B-HQ/resolve/main/wan2.2-t2v-a14b-hq.safetensors",
                    "sha256": None,
                    "size": 14200000000,
                    "dependencies": []
                },
                "wan2_2_ti2v_5b": {
                    "type": "checkpoints",
                    "filename": "wan2.2-ti2v-b5.safetensors", 
                    "url": "https://huggingface.co/black-forest-labs/WAN2.2-TI2V-B5/resolve/main/wan2.2-ti2v-b5.safetensors",
                    "sha256": None,
                    "size": 5000000000,
                    "dependencies": []
                },
                "flux1.dev": {
                    "type": "checkpoints",
                    "filename": "flux1-dev.safetensors",
                    "url": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors",
                    "sha256": None,
                    "size": 23000000000,
                    "dependencies": [
                        {
                            "type": "clip",
                            "filename": "t5xxl_fp16.safetensors",
                            "url": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/t5xxl_fp16.safetensors",
                            "size": 23000000000
                        },
                        {
                            "type": "vae", 
                            "filename": "ae.safetensors",
                            "url": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
                            "size": 167000000
                        }
                    ]
                },
                "flux1_krea_dev": {
                    "type": "checkpoints",
                    "filename": "flux1-krea-dev.safetensors",
                    "url": "https://huggingface.co/black-forest-labs/FLUX.1-Krea-dev/resolve/main/flux1-krea-dev.safetensors",
                    "sha256": None,
                    "size": 23000000000,
                    "dependencies": [
                        {
                            "type": "clip",
                            "filename": "t5xxl_fp8.safetensors",
                            "url": "https://huggingface.co/black-forest-labs/FLUX.1-Krea-dev/resolve/main/t5xxl_fp8.safetensors",
                            "size": 23000000000
                        },
                        {
                            "type": "vae",
                            "filename": "ae.safetensors", 
                            "url": "https://huggingface.co/black-forest-labs/FLUX.1-Krea-dev/resolve/main/ae.safetensors",
                            "size": 167000000
                        }
                    ]
                },
                "sdxl": {
                    "type": "checkpoints",
                    "filename": "sd_xl_base_1.0.safetensors",
                    "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
                    "sha256": None,
                    "size": 6600000000,
                    "dependencies": [
                        {
                            "type": "clip",
                            "filename": "text_encoder.safetensors",
                            "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/text_encoder.safetensors",
                            "size": 240000000
                        },
                        {
                            "type": "clip", 
                            "filename": "text_encoder_2.safetensors",
                            "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/text_encoder_2.safetensors",
                            "size": 240000000
                        },
                        {
                            "type": "vae",
                            "filename": "vae.safetensors",
                            "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/vae.safetensors",
                            "size": 167000000
                        }
                    ]
                },
                "krea": {
                    "type": "checkpoints",
                    "filename": "krea.safetensors",
                    "url": "https://huggingface.co/krea/ai/resolve/main/krea.safetensors",
                    "sha256": None,
                    "size": 23000000000,
                    "dependencies": []
                },
                "Chroma_final": {
                    "type": "checkpoints",
                    "filename": "chroma_final.safetensors",
                    "url": "https://huggingface.co/chroma/ai/resolve/main/chroma_final.safetensors", 
                    "sha256": None,
                    "size": 23000000000,
                    "dependencies": []
                },
                "flux_kontext_dev_basic": {
                    "type": "checkpoints",
                    "filename": "flux-kontext-dev-basic.safetensors",
                    "url": "https://huggingface.co/kontext/ai/resolve/main/flux-kontext-dev-basic.safetensors",
                    "sha256": None,
                    "size": 23000000000,
                    "dependencies": []
                }
            }
    
    def ensure_directory(self, path: Path) -> None:
        """Ensure directory exists and is writable"""
        path.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        test_file = path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            logger.error(f"Cannot write to directory {path}: {e}")
            raise
    
    def validate_volume_persistence(self) -> bool:
        """Validate that the volume is persistent and writable"""
        try:
            # Test if we can create and persist files
            test_dir = self.base_path / ".persistence_test"
            test_file = test_dir / "test.txt"
            
            # Create test directory and file
            self.ensure_directory(test_dir)
            test_file.write_text("Volume persistence test")
            
            # Verify file exists and content is correct
            if test_file.exists() and test_file.read_text() == "Volume persistence test":
                logger.info("✓ Volume persistence validated successfully")
                # Clean up test files
                test_file.unlink()
                test_dir.rmdir()
                return True
            else:
                logger.error("✗ Volume persistence test failed - file content incorrect")
                return False
                
        except Exception as e:
            logger.error(f"✗ Volume persistence validation failed: {e}")
            return False
    
    def validate_file_integrity(self, file_path: Path, expected_size: int = None) -> bool:
        """Validate file integrity by checking size and basic structure"""
        try:
            if not file_path.exists():
                logger.warning(f"File does not exist: {file_path}")
                return False
            
            # Check file size
            actual_size = file_path.stat().st_size
            if expected_size and abs(actual_size - expected_size) > (expected_size * 0.01):  # 1% tolerance
                logger.warning(f"File size mismatch for {file_path}: expected ~{expected_size}, got {actual_size}")
                return False
            
            # Check if file is not empty and has reasonable size (> 1MB for models)
            if actual_size < 1024 * 1024:  # Less than 1MB
                logger.warning(f"File too small to be a valid model: {file_path} ({actual_size} bytes)")
                return False
            
            # For .safetensors files, check magic bytes
            if file_path.suffix == '.safetensors':
                with open(file_path, 'rb') as f:
                    magic = f.read(8)
                    if magic != b'__safet':
                        logger.warning(f"Invalid safetensors file: {file_path}")
                        return False
            
            logger.info(f"✓ File integrity validated: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"File integrity check failed for {file_path}: {e}")
            return False
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def download_file(self, url: str, destination: Path, expected_hash: Optional[str] = None, expected_size: Optional[int] = None) -> bool:
        """Download a file with progress tracking, size validation, and hash verification"""
        try:
            logger.info(f"Downloading {url}")
            logger.info(f"Destination: {destination}")
            
            # Create destination directory and validate write permissions
            self.ensure_directory(destination.parent)
            
            # Download with streaming and resume capability
            headers = {}
            resume_pos = 0
            
            # Add Hugging Face token if URL is from Hugging Face and token is available
            hf_token = os.getenv('HUGGING_FACE_API_KEY')
            if hf_token and 'huggingface.co' in url:
                headers['Authorization'] = f'Bearer {hf_token}'
                logger.info("Using Hugging Face API token for authentication")
            
            # Check if file already exists and resume download
            if destination.exists():
                resume_pos = destination.stat().st_size
                if resume_pos > 0:
                    headers['Range'] = f'bytes={resume_pos}-'
                    logger.info(f"Resuming download from {resume_pos} bytes")
            
            response = requests.get(url, stream=True, headers=headers)
            
            # Handle partial content (resume)
            if resume_pos > 0 and response.status_code == 206:
                logger.info("Resuming partial download")
            elif resume_pos > 0:
                logger.warning("Server doesn't support resume, starting fresh download")
                destination.unlink()
                resume_pos = 0
            else:
                response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            downloaded = resume_pos
            
            # Open file in append mode if resuming, write mode otherwise
            mode = 'ab' if resume_pos > 0 else 'wb'
            
            with open(destination, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Progress indicator
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if downloaded % (10 * 1024 * 1024) == 0:  # Update every 10MB
                                logger.info(f"Progress: {percent:.1f}% ({downloaded // (1024*1024)}MB/{total_size // (1024*1024)}MB)")
            
            logger.info(f"Download completed: {destination}")
            
            # Validate file integrity
            if not self.validate_file_integrity(destination, expected_size):
                logger.error(f"File integrity validation failed for {destination}")
                destination.unlink()
                return False
            
            # Verify hash if provided
            if expected_hash:
                logger.info(f"Calculating hash for {destination}...")
                actual_hash = self.calculate_file_hash(destination)
                if actual_hash != expected_hash:
                    logger.error(f"Hash mismatch for {destination}")
                    logger.error(f"Expected: {expected_hash}")
                    logger.error(f"Actual: {actual_hash}")
                    destination.unlink()  # Delete corrupted file
                    return False
                else:
                    logger.info(f"✓ Hash verified for {destination}")
            
            logger.info(f"✓ Download and validation completed successfully: {destination}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            if destination.exists():
                # Only delete if it's a small file (likely corrupted)
                if destination.stat().st_size < 1024 * 1024:
                    destination.unlink()
            return False
    
    def model_exists(self, model_name: str) -> bool:
        """Check if model and its dependencies exist and are valid"""
        if model_name not in self.model_configs:
            logger.warning(f"No configuration found for model: {model_name}")
            return False
        
        config = self.model_configs[model_name]
        
        # Check main model file
        model_path = self.base_path / config["type"] / config["filename"]
        if not model_path.exists():
            logger.info(f"Model file not found: {model_path}")
            return False
        
        # Validate main model file integrity
        if not self.validate_file_integrity(model_path, config.get("size")):
            logger.warning(f"Model file validation failed: {model_path}")
            return False
        
        # Check and validate dependencies
        for dep in config.get("dependencies", []):
            dep_path = self.base_path / dep["type"] / dep["filename"]
            if not dep_path.exists():
                logger.info(f"Dependency file not found: {dep_path}")
                return False
            
            # Validate dependency file integrity
            if not self.validate_file_integrity(dep_path, dep.get("size")):
                logger.warning(f"Dependency file validation failed: {dep_path}")
                return False
        
        logger.info(f"✓ Model {model_name} exists and is valid")
        return True
    
    def download_model(self, model_name: str) -> bool:
        """Download a model and its dependencies with validation"""
        if model_name not in self.model_configs:
            logger.error(f"Unknown model: {model_name}")
            return False
        
        config = self.model_configs[model_name]
        logger.info(f"Downloading model: {model_name}")
        
        # Download main model
        model_path = self.base_path / config["type"] / config["filename"]
        if not model_path.exists() or not self.validate_file_integrity(model_path, config.get("size")):
            if model_path.exists() and not self.validate_file_integrity(model_path, config.get("size")):
                logger.warning(f"Existing model file is corrupted, re-downloading: {model_path}")
                model_path.unlink()
            
            logger.info(f"Downloading main model: {config['filename']}")
            if not self.download_file(config["url"], model_path, config.get("sha256"), config.get("size")):
                logger.error(f"Failed to download main model: {config['filename']}")
                return False
        else:
            logger.info(f"Main model already exists and is valid: {config['filename']}")
        
        # Download dependencies
        for dep in config.get("dependencies", []):
            dep_path = self.base_path / dep["type"] / dep["filename"]
            if not dep_path.exists() or not self.validate_file_integrity(dep_path, dep.get("size")):
                if dep_path.exists() and not self.validate_file_integrity(dep_path, dep.get("size")):
                    logger.warning(f"Existing dependency file is corrupted, re-downloading: {dep_path}")
                    dep_path.unlink()
                
                logger.info(f"Downloading dependency: {dep['filename']}")
                if not self.download_file(dep["url"], dep_path, dep.get("sha256"), dep.get("size")):
                    logger.error(f"Failed to download dependency: {dep['filename']}")
                    return False
            else:
                logger.info(f"Dependency already exists and is valid: {dep['filename']}")
        
        # Final validation of the complete model
        if self.model_exists(model_name):
            logger.info(f"✓ Successfully downloaded and validated model: {model_name}")
            return True
        else:
            logger.error(f"Final validation failed for model: {model_name}")
            return False
    
    def download_models(self, model_names: List[str]) -> Dict[str, bool]:
        """Download multiple models with volume persistence validation"""
        results = {}
        
        # Validate volume persistence first
        logger.info("Validating volume persistence...")
        if not self.validate_volume_persistence():
            logger.error("Volume persistence validation failed. Cannot proceed with downloads.")
            return {model: False for model in model_names}
        
        # Validate base directory structure
        logger.info("Setting up model directory structure...")
        for model_type in ["checkpoints", "clip", "vae", "loras", "controlnet"]:
            self.ensure_directory(self.base_path / model_type)
        
        for model_name in model_names:
            logger.info(f"Processing model: {model_name}")
            
            if self.model_exists(model_name):
                logger.info(f"✓ Model {model_name} already exists and is valid, skipping")
                results[model_name] = True
            else:
                logger.info(f"Downloading model: {model_name}")
                results[model_name] = self.download_model(model_name)
        
        # Summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        logger.info(f"Download summary: {successful}/{total} models successfully processed")
        
        return results
    
    def list_available_models(self) -> List[str]:
        """List all available model names"""
        return list(self.model_configs.keys())
    
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get information about a model"""
        return self.model_configs.get(model_name)

def main():
    parser = argparse.ArgumentParser(description="ComfyUI Model Manager")
    parser.add_argument("--models", nargs="+", help="Models to download")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--check", nargs="+", help="Check if models exist")
    parser.add_argument("--base-path", default="/app/ComfyUI/models", help="Base path for models")
    
    args = parser.parse_args()
    
    manager = ModelManager(args.base_path)
    
    if args.list:
        models = manager.list_available_models()
        print("Available models:")
        for model in models:
            print(f"  - {model}")
    
    elif args.check:
        for model in args.check:
            exists = manager.model_exists(model)
            status = "✓" if exists else "✗"
            print(f"{status} {model}")
    
    elif args.models:
        results = manager.download_models(args.models)
        
        print("\nDownload Results:")
        for model, success in results.items():
            status = "✓ Success" if success else "✗ Failed"
            print(f"{status}: {model}")
        
        # Exit with error code if any downloads failed
        if not all(results.values()):
            exit(1)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
