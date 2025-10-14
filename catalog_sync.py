#!/usr/bin/env python3
"""
Bulletproof Model Catalog Sync Service
Automatically syncs with grid-image-model-reference repository to ensure catalog accuracy.
"""

import os
import json
import time
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/catalog_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CatalogSyncService:
    def __init__(self):
        self.repo_url = "https://github.com/AI-Power-Grid/grid-image-model-reference"
        self.local_repo_path = "/app/grid-image-model-reference"
        self.catalog_path = "/app/comfy-bridge/model_configs.json"
        self.backup_path = "/app/comfy-bridge/model_configs.json.backup"
        self.last_sync_file = "/app/comfy-bridge/.last_catalog_sync"
        self.sync_interval = 300  # 5 minutes
        self.max_retries = 3
        self.timeout = 30
        
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last sync timestamp."""
        try:
            if os.path.exists(self.last_sync_file):
                with open(self.last_sync_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.warning(f"Could not read last sync time: {e}")
        return None
    
    def update_last_sync_time(self):
        """Update the last sync timestamp."""
        try:
            with open(self.last_sync_file, 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.warning(f"Could not update last sync time: {e}")
    
    def should_sync(self) -> bool:
        """Check if we should sync based on time interval."""
        last_sync = self.get_last_sync_time()
        if last_sync is None:
            return True
        
        time_since_sync = datetime.now() - last_sync
        return time_since_sync.total_seconds() > self.sync_interval
    
    def backup_catalog(self):
        """Create a backup of the current catalog."""
        try:
            if os.path.exists(self.catalog_path):
                subprocess.run(['cp', self.catalog_path, self.backup_path], check=True)
                logger.info("Catalog backup created")
        except Exception as e:
            logger.error(f"Failed to backup catalog: {e}")
    
    def restore_catalog(self):
        """Restore catalog from backup."""
        try:
            if os.path.exists(self.backup_path):
                subprocess.run(['cp', self.backup_path, self.catalog_path], check=True)
                logger.info("Catalog restored from backup")
                return True
        except Exception as e:
            logger.error(f"Failed to restore catalog: {e}")
        return False
    
    def validate_catalog(self, catalog: Dict[str, Any]) -> bool:
        """Validate catalog structure and content."""
        try:
            if not isinstance(catalog, dict):
                logger.error("Catalog is not a dictionary")
                return False
            
            if len(catalog) == 0:
                logger.error("Catalog is empty")
                return False
            
            # Check each model entry
            for model_id, model_info in catalog.items():
                if not isinstance(model_info, dict):
                    logger.error(f"Model {model_id} info is not a dictionary")
                    return False
                
                required_fields = ['type', 'filename', 'url', 'size_mb', 'description']
                for field in required_fields:
                    if field not in model_info:
                        logger.error(f"Model {model_id} missing required field: {field}")
                        return False
                
                # Validate URL
                url = model_info.get('url', '')
                if not url or not url.startswith('http'):
                    logger.error(f"Model {model_id} has invalid URL: {url}")
                    return False
                
                # Validate size
                size_mb = model_info.get('size_mb', 0)
                if not isinstance(size_mb, (int, float)) or size_mb <= 0:
                    logger.error(f"Model {model_id} has invalid size: {size_mb}")
                    return False
            
            logger.info(f"Catalog validation passed: {len(catalog)} models")
            return True
            
        except Exception as e:
            logger.error(f"Catalog validation failed: {e}")
            return False
    
    def fetch_repo_catalog(self) -> Optional[Dict[str, Any]]:
        """Fetch catalog from grid-image-model-reference repository."""
        try:
            # Try to get the latest stable_diffusion.json from the repo
            url = f"{self.repo_url}/raw/main/stable_diffusion.json"
            
            logger.info(f"Fetching catalog from: {url}")
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            catalog = response.json()
            logger.info(f"Successfully fetched catalog with {len(catalog)} models")
            return catalog
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch catalog from repository: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse catalog JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching catalog: {e}")
            return None
    
    def convert_repo_catalog(self, repo_catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Convert repository catalog format to our internal format."""
        converted = {}
        
        for model_id, model_info in repo_catalog.items():
            try:
                # Extract download information
                config = model_info.get('config', {})
                files = config.get('files', [])
                download_url = config.get('download_url', '')
                
                if not files and not download_url:
                    logger.warning(f"Model {model_id} has no download information, skipping")
                    continue
                
                # Get the main file (usually the first one)
                main_file = files[0] if files else {}
                filename = main_file.get('path', '') or download_url.split('/')[-1] if download_url else f"{model_id}.safetensors"
                
                # Determine file type
                file_type = main_file.get('file_type', 'checkpoints')
                if not file_type or file_type == 'unknown':
                    # Infer from filename
                    if 'vae' in filename.lower():
                        file_type = 'vae'
                    elif 'lora' in filename.lower():
                        file_type = 'loras'
                    elif 'clip' in filename.lower():
                        file_type = 'clip'
                    else:
                        file_type = 'checkpoints'
                
                # Estimate size if not provided
                size_mb = model_info.get('size_on_disk_bytes', 0) / (1024 * 1024) if model_info.get('size_on_disk_bytes') else 4000
                
                # Determine capability type
                capability_type = self.get_capability_type(model_info)
                
                converted[model_id] = {
                    'type': file_type,
                    'filename': filename,
                    'url': download_url or main_file.get('file_url', ''),
                    'sha256': main_file.get('sha256sum'),
                    'size_mb': int(size_mb),
                    'description': model_info.get('description', ''),
                    'capability_type': capability_type,
                    'dependencies': []
                }
                
            except Exception as e:
                logger.error(f"Error converting model {model_id}: {e}")
                continue
        
        logger.info(f"Converted {len(converted)} models from repository catalog")
        return converted
    
    def get_capability_type(self, model_info: Dict[str, Any]) -> str:
        """Determine model capability type."""
        style = model_info.get('style', '').lower()
        baseline = model_info.get('baseline', '').lower()
        description = model_info.get('description', '').lower()
        inpainting = model_info.get('inpainting', False)
        
        # Video models
        if 'video' in style or 'wan' in baseline:
            if inpainting or 'image-to-video' in description:
                return 'Image-to-Video'
            return 'Text-to-Video'
        
        # Image models
        if inpainting or 'image-to-image' in description or 'img2img' in description:
            return 'Image-to-Image'
        
        return 'Text-to-Image'
    
    def merge_catalogs(self, current_catalog: Dict[str, Any], new_catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Merge new catalog with current catalog, preserving user customizations."""
        merged = new_catalog.copy()
        
        # Preserve any custom models that aren't in the new catalog
        for model_id, model_info in current_catalog.items():
            if model_id not in merged:
                # Check if this looks like a custom model (not from the repo)
                if not model_info.get('url', '').startswith('https://huggingface.co'):
                    logger.info(f"Preserving custom model: {model_id}")
                    merged[model_id] = model_info
        
        return merged
    
    def sync_catalog(self) -> bool:
        """Main sync method."""
        try:
            logger.info("Starting catalog sync...")
            
            # Check if we should sync
            if not self.should_sync():
                logger.info("Sync not needed yet")
                return True
            
            # Backup current catalog
            self.backup_catalog()
            
            # Fetch new catalog from repository
            repo_catalog = self.fetch_repo_catalog()
            if repo_catalog is None:
                logger.error("Failed to fetch repository catalog")
                return False
            
            # Convert to our format
            new_catalog = self.convert_repo_catalog(repo_catalog)
            if not new_catalog:
                logger.error("Failed to convert repository catalog")
                return False
            
            # Validate new catalog
            if not self.validate_catalog(new_catalog):
                logger.error("New catalog validation failed")
                return False
            
            # Load current catalog for merging
            current_catalog = {}
            try:
                if os.path.exists(self.catalog_path):
                    with open(self.catalog_path, 'r') as f:
                        current_catalog = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load current catalog: {e}")
            
            # Merge catalogs
            merged_catalog = self.merge_catalogs(current_catalog, new_catalog)
            
            # Validate merged catalog
            if not self.validate_catalog(merged_catalog):
                logger.error("Merged catalog validation failed")
                return False
            
            # Write new catalog
            with open(self.catalog_path, 'w') as f:
                json.dump(merged_catalog, f, indent=2)
            
            # Update sync timestamp
            self.update_last_sync_time()
            
            logger.info(f"Catalog sync completed successfully: {len(merged_catalog)} models")
            return True
            
        except Exception as e:
            logger.error(f"Catalog sync failed: {e}")
            # Try to restore from backup
            if self.restore_catalog():
                logger.info("Catalog restored from backup after sync failure")
            return False
    
    def run_continuous_sync(self):
        """Run continuous sync in a loop."""
        logger.info("Starting continuous catalog sync service...")
        
        while True:
            try:
                self.sync_catalog()
                time.sleep(self.sync_interval)
            except KeyboardInterrupt:
                logger.info("Sync service stopped by user")
                break
            except Exception as e:
                logger.error(f"Sync service error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        # Run continuous sync
        service = CatalogSyncService()
        service.run_continuous_sync()
    else:
        # Run single sync
        service = CatalogSyncService()
        success = service.sync_catalog()
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
