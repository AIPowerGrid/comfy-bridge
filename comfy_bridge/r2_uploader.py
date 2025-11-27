import logging
import httpx

logger = logging.getLogger(__name__)


class R2Uploader:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    async def upload_video(self, upload_url: str, video_bytes: bytes) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Content-Type": "video/mp4"}
                response = await client.put(
                    upload_url, content=video_bytes, headers=headers
                )
                response.raise_for_status()
                logger.info("R2 upload successful")
                return True
        except Exception as e:
            logger.warning(f"R2 upload failed: {e}")
            return False

