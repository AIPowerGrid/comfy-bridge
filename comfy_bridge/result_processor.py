import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Constants
MIN_VIDEO_SIZE_BYTES = 100 * 1024  # 100KB minimum for valid video file


class ResultProcessor:
    def __init__(self, comfy_client):
        self.comfy = comfy_client
    
    async def process_outputs(
        self, outputs: Dict[str, Any], model_name: str
    ) -> Optional[tuple[bytes, str, str]]:
        for node_id, node_data in outputs.items():
            # Handle videos
            videos = node_data.get("videos", [])
            if videos:
                result = await self._process_video(videos[0]["filename"])
                if result:
                    return result
            
            # Handle images (check if they're actually videos)
            imgs = node_data.get("images", [])
            if imgs:
                result = await self._process_image_or_video(
                    imgs[0]["filename"], model_name
                )
                if result:
                    return result
        
        return None
    
    async def _process_video(self, filename: str) -> Optional[tuple[bytes, str, str]]:
        try:
            media_bytes = await self.comfy.get_file(filename)
            
            if len(media_bytes) >= MIN_VIDEO_SIZE_BYTES:
                logger.info(f"Found complete video: {filename}")
                return (media_bytes, "video", filename)
        except Exception as e:
            logger.error(f"Failed to fetch video file: {e}")
        
        return None
    
    async def _process_image_or_video(
        self, filename: str, model_name: str
    ) -> Optional[tuple[bytes, str, str]]:
        if filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
            # Video file in images array
            return await self._process_video(filename)
        
        # Actual image
        if model_name and 'wan2' in model_name.lower():
            return None  # Skip images for video jobs
        
        try:
            media_bytes = await self.comfy.get_file(filename)
            logger.info(f"Found complete image: {filename}")
            return (media_bytes, "image", filename)
        except Exception as e:
            logger.error(f"Failed to fetch image file: {e}")
            return None

