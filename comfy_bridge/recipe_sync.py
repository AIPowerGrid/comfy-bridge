"""
Recipe Sync Service - Downloads recipes from RecipesVault and stores them locally.
Syncs recipes every 12 hours and saves them as JSON files in the workflows directory.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from .config import Settings
from .recipesvault_client import get_recipesvault_client, OnChainRecipeInfo

logger = logging.getLogger(__name__)

# Sync interval: 12 hours in seconds
SYNC_INTERVAL_SECONDS = 12 * 60 * 60  # 12 hours


class RecipeSyncService:
    """Service to sync recipes from RecipesVault to local files."""
    
    def __init__(self):
        self.workflow_dir = Path(Settings.WORKFLOW_DIR)
        self.last_sync_time: Optional[datetime] = None
        self.sync_lock = asyncio.Lock()
        self._sync_task: Optional[asyncio.Task] = None
        
    async def sync_recipes(self, force: bool = False) -> Dict[str, bool]:
        """
        Download all recipes from RecipesVault and save them as JSON files.
        
        Args:
            force: If True, sync even if recently synced
            
        Returns:
            Dict mapping recipe names to success status
        """
        async with self.sync_lock:
            # Check if we need to sync
            if not force and self.last_sync_time:
                time_since_sync = datetime.now() - self.last_sync_time
                if time_since_sync < timedelta(seconds=SYNC_INTERVAL_SECONDS):
                    logger.debug(f"Skipping sync - last sync was {time_since_sync} ago")
                    return {}
            
            if not Settings.RECIPESVAULT_ENABLED or not Settings.RECIPESVAULT_CONTRACT:
                logger.debug("RecipesVault not enabled or contract not configured")
                return {}
            
            try:
                client = get_recipesvault_client()
                if not client.enabled:
                    logger.warning("RecipesVault client not enabled")
                    return {}
                
                logger.info("Starting recipe sync from RecipesVault...")
                recipes = client.fetch_all_recipes(force_refresh=True)
                
                results = {}
                synced_count = 0
                failed_count = 0
                
                # Ensure workflow directory exists
                self.workflow_dir.mkdir(parents=True, exist_ok=True)
                
                for recipe_name, recipe_info in recipes.items():
                    try:
                        # Skip duplicates (same recipe_name might appear multiple times)
                        if recipe_name in results:
                            continue
                            
                        # Save recipe as JSON file
                        filename = self._get_workflow_filename(recipe_info.recipe_name)
                        filepath = self.workflow_dir / filename
                        
                        # Parse workflow JSON
                        workflow_dict = recipe_info.get_workflow_dict()
                        if not workflow_dict:
                            logger.warning(f"Failed to parse workflow JSON for recipe '{recipe_info.recipe_name}'")
                            results[recipe_name] = False
                            failed_count += 1
                            continue
                        
                        # Save to file
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(workflow_dict, f, indent=2, ensure_ascii=False)
                        
                        logger.debug(f"Synced recipe '{recipe_info.recipe_name}' -> {filename}")
                        results[recipe_name] = True
                        synced_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to sync recipe '{recipe_name}': {e}")
                        results[recipe_name] = False
                        failed_count += 1
                
                self.last_sync_time = datetime.now()
                logger.info(f"Recipe sync completed: {synced_count} synced, {failed_count} failed")
                
                return results
                
            except Exception as e:
                logger.error(f"Error during recipe sync: {e}")
                return {}
    
    def _get_workflow_filename(self, recipe_name: str) -> str:
        """Convert recipe name to workflow filename."""
        # Normalize recipe name to filename
        # Remove special characters, replace spaces with underscores
        filename = recipe_name.replace(" ", "_").replace(".", "_").replace("-", "_")
        # Ensure it ends with .json
        if not filename.endswith('.json'):
            filename += '.json'
        return filename
    
    async def start_periodic_sync(self):
        """Start background task to sync recipes every 12 hours."""
        if self._sync_task and not self._sync_task.done():
            logger.debug("Periodic sync already running")
            return
        
        async def sync_loop():
            logger.info("Starting periodic recipe sync (every 12 hours)")
            # Initial sync
            await self.sync_recipes(force=True)
            
            # Then sync every 12 hours
            while True:
                try:
                    await asyncio.sleep(SYNC_INTERVAL_SECONDS)
                    await self.sync_recipes(force=False)
                except asyncio.CancelledError:
                    logger.info("Periodic recipe sync cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in periodic recipe sync: {e}")
                    # Continue syncing even if one fails
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        self._sync_task = asyncio.create_task(sync_loop())
        logger.info("Periodic recipe sync task started")
    
    async def stop_periodic_sync(self):
        """Stop the periodic sync task."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            logger.info("Periodic recipe sync stopped")
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last sync time."""
        return self.last_sync_time


# Global instance
_recipe_sync_service: Optional[RecipeSyncService] = None


def get_recipe_sync_service() -> RecipeSyncService:
    """Get singleton RecipeSyncService instance."""
    global _recipe_sync_service
    if _recipe_sync_service is None:
        _recipe_sync_service = RecipeSyncService()
    return _recipe_sync_service

