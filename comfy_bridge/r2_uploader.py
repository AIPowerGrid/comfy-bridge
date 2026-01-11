import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class R2Uploader:
    def __init__(self, timeout: int = 120):  # 2 minutes (4x increase for larger video files)
        self.timeout = timeout

    async def upload_video(self, upload_url: str, video_bytes: bytes, filename: Optional[str] = None, media_type: str = "video") -> bool:
        """Upload video to R2. For images, use upload_image instead."""
        # IMPORTANT: Do NOT modify presigned URL paths - it invalidates the signature!
        # Presigned URLs cryptographically sign the entire request including the path.
        # Modifying the path (e.g., changing .webp to .mp4) will cause signature validation to fail.
        # 
        # The API should provide video-specific presigned URLs, but if it doesn't:
        # 1. We upload to the URL as-provided (even if it's .webp)
        # 2. The payload builder will construct the correct download URL separately
        # 3. The file will be stored at the presigned URL path, but we'll reference it correctly in the payload
        
        # Warn if presigned URL ends in .webp for videos (this is a problem)
        base_url = upload_url.split("?")[0] if "?" in upload_url else upload_url
        if base_url.endswith('.webp'):
            logger.warning(f"Video upload: Presigned URL ends in .webp (expected .mp4 for videos)")
            logger.warning(f"  Upload URL: {upload_url[:100]}...")
            logger.warning(f"  The file will be uploaded to .webp path, but download URL will point to .mp4")
            logger.warning(f"  This may cause issues - the API should provide video-specific presigned URLs")
        else:
            logger.info(f"Video upload: Using presigned URL as-provided (path modification would invalidate signature)")
        
        return await self._upload_media(upload_url, video_bytes, filename, media_type)
    
    async def upload_image(self, upload_url: str, image_bytes: bytes, filename: Optional[str] = None) -> bool:
        """Upload image to R2."""
        return await self._upload_media(upload_url, image_bytes, filename, "image")
    
    async def _upload_media(self, upload_url: str, media_bytes: bytes, filename: Optional[str] = None, media_type: str = "video") -> bool:
        """Generic method to upload media (video or image) to R2."""
        try:
            # Display file metadata
            file_size_mb = len(media_bytes) / (1024 * 1024)
            
            # Validate video file format (check for MP4 file signature)
            if media_type == "video":
                # MP4 files start with ftyp box: bytes 4-8 should be "ftyp"
                # Then bytes 8-12 contain the brand (e.g., "isom", "mp41", "mp42")
                if len(media_bytes) < 12:
                    logger.error(f"Video file too small ({len(media_bytes)} bytes) - may be corrupted")
                    return False
                
                # Check for MP4 file signature (ftyp box)
                if media_bytes[4:8] != b'ftyp':
                    logger.warning(f"Video file doesn't have MP4 signature (ftyp box) - may not be valid MP4")
                    logger.warning(f"First 12 bytes: {media_bytes[:12].hex()}")
                    # Don't fail - some valid MP4s might have different structure
                else:
                    brand = media_bytes[8:12].decode('ascii', errors='ignore')
                    logger.info(f"Video file validated - MP4 brand: {brand}")
            
            # Determine content type based on media type and filename
            if media_type == "image":
                # Determine image content type from filename extension
                if filename:
                    ext = filename.lower().split('.')[-1] if '.' in filename else ''
                    if ext == 'png':
                        content_type = "image/png"
                    elif ext == 'jpg' or ext == 'jpeg':
                        content_type = "image/jpeg"
                    elif ext == 'webp':
                        content_type = "image/webp"
                    else:
                        content_type = "image/png"  # Default to PNG
                else:
                    content_type = "image/png"
            elif media_type == "video":
                content_type = "video/mp4"
            else:
                content_type = "application/octet-stream"

            logger.info(f"R2 Upload - File: {filename or 'unknown'}")
            logger.info(f"R2 Upload - Size: {file_size_mb:.2f} MB ({len(media_bytes):,} bytes)")
            logger.info(f"R2 Upload - Type: {media_type} ({content_type})")
            logger.info("R2 Upload - Starting upload...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Content-Type": content_type,
                    "Content-Length": str(len(media_bytes))
                }

                response = await client.put(
                    upload_url,
                    content=media_bytes,
                    headers=headers
                )
                
                # Check for signature validation errors (403 Forbidden)
                if response.status_code == 403:
                    error_text = response.text[:500] if response.text else ""
                    logger.error(f"R2 upload failed with 403 Forbidden - signature validation failed")
                    logger.error(f"This usually means the presigned URL path was modified or expired")
                    logger.error(f"Upload URL: {upload_url[:100]}...")
                    logger.error(f"Error: {error_text}")
                    response.raise_for_status()
                
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

