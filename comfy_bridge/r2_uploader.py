import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class R2Uploader:
    def __init__(self, timeout: int = 120):  # 2 minutes (4x increase for larger video files)
        self.timeout = timeout

    async def upload_video(self, upload_url: str, video_bytes: bytes, filename: Optional[str] = None, media_type: str = "video") -> bool:
        try:
            # Display file metadata
            file_size_mb = len(video_bytes) / (1024 * 1024)
            content_type = "video/mp4" if media_type == "video" else f"application/octet-stream"

            logger.info(f"R2 Upload - File: {filename or 'unknown'}")
            logger.info(f"R2 Upload - Size: {file_size_mb:.2f} MB ({len(video_bytes):,} bytes)")
            logger.info(f"R2 Upload - Type: {media_type} ({content_type})")
            logger.info("R2 Upload - Starting upload...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Content-Type": content_type,
                    "Content-Length": str(len(video_bytes))
                }

                response = await client.put(
                    upload_url,
                    content=video_bytes,
                    headers=headers
                )
                response.raise_for_status()

                # Extract filename from URL if not provided
                r2_filename = filename
                if not r2_filename:
                    # Try to extract filename from URL path
                    from urllib.parse import urlparse
                    parsed_url = urlparse(upload_url)
                    path_parts = parsed_url.path.strip('/').split('/')
                    if path_parts:
                        r2_filename = path_parts[-1]

                logger.info(f"R2 Upload - SUCCESS: File '{r2_filename or 'unknown'}' uploaded to R2 ({file_size_mb:.2f} MB)")
                return True

        except Exception as e:
            logger.warning(f"R2 upload failed: {e}")
            return False

