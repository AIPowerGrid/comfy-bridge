import glob
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from .config import Settings

logger = logging.getLogger(__name__)

# Constants
MIN_VIDEO_SIZE_BYTES = 100 * 1024  # 100KB minimum for valid video file


class FilesystemChecker:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Settings.COMFYUI_OUTPUT_DIR
    
    async def check_for_completed_file(
        self, job_id: str
    ) -> Optional[Tuple[bytes, str, str]]:
        logger.info(f"Checking filesystem for complete files for job {job_id}")
        expected_prefix = f"horde_{job_id}"
        
        search_patterns = [
            f"{self.output_dir}/{expected_prefix}*.mp4",
            f"{self.output_dir}/*{job_id}*.mp4",
        ]
        
        video_files = []
        for pattern in search_patterns:
            files = glob.glob(pattern, recursive=True)
            for file_path in files:
                if Path(file_path).suffix.lower() in [
                    '.mp4', '.webm', '.avi', '.mov', '.mkv'
                ]:
                    try:
                        file_size = os.path.getsize(file_path)
                        video_files.append((
                            file_path, Path(file_path).name, file_size
                        ))
                    except OSError:
                        continue
        
        if not video_files:
            return None
        
        # Sort by file size (largest first)
        video_files.sort(key=lambda x: x[2], reverse=True)
        video_path, filename, file_size = video_files[0]
        
        with open(video_path, 'rb') as f:
            media_bytes = f.read()
        
        # Validate file size
        if len(media_bytes) < MIN_VIDEO_SIZE_BYTES:
            return None
        
        logger.info(f"Found complete video: {len(media_bytes)} bytes")
        
        # Wait for file to be completely written
        await asyncio.sleep(2)
        with open(video_path, 'rb') as f:
            new_media_bytes = f.read()
        
        return (new_media_bytes, "video", filename)
