import logging
from typing import Dict, Any
from .utils import encode_media

logger = logging.getLogger(__name__)

# Constants
BYTES_PER_MB = 1024 * 1024
MAX_B64_SIZE_MB = 10  # Warn if base64 payload exceeds this size


class PayloadBuilder:
    def build_payload(
        self, job: Dict[str, Any], media_bytes: bytes, 
        media_type: str, filename: str
    ) -> Dict[str, Any]:
        job_id = job.get("id")
        r2_upload_url = job.get("r2_upload")
        
        # For videos with R2 upload, use special handling
        if media_type == "video" and r2_upload_url:
            return self._build_video_r2_payload(
                job, media_bytes, filename, r2_upload_url
            )
        
        # Standard payload for images or videos without R2
        return self._build_standard_payload(job, media_bytes, media_type, filename)
    
    def _build_video_r2_payload(
        self, job: Dict[str, Any], media_bytes: bytes, 
        filename: str, r2_upload_url: str
    ) -> Dict[str, Any]:
        job_id = job.get("id")
        original_filename = self._ensure_mp4_extension(filename, job_id)
        
        # Get r2_uploads array from job, or construct from r2_upload URL
        r2_uploads = job.get("r2_uploads", [])
        if not r2_uploads and r2_upload_url:
            # Construct r2_uploads array from the upload URL
            # The API expects an array of upload info objects
            r2_uploads = [{"url": r2_upload_url}]
        
        payload = {
            "id": job_id,
            "state": "ok",
            "seed": int(job.get("payload", {}).get("seed", 0)),
            "filename": original_filename,
            "form": "video",
            "type": "video",
            "media_type": "video"
        }
        
        # Encode video to base64 (always needed for API submission)
        b64 = encode_media(media_bytes, "video")
        b64_size_mb = len(b64) / BYTES_PER_MB
        
        if b64_size_mb > MAX_B64_SIZE_MB:
            logger.warning(f"Base64 video size is {b64_size_mb:.1f}MB - this may cause API errors")
        
        payload["generation"] = b64
        
        # Include r2_uploads if available
        if r2_uploads:
            payload["r2_uploads"] = r2_uploads
        else:
            logger.warning("No r2_uploads array or r2_upload URL found, using base64 generation only")
        
        return payload
    
    def _build_standard_payload(
        self, job: Dict[str, Any], media_bytes: bytes, 
        media_type: str, filename: str
    ) -> Dict[str, Any]:
        job_id = job.get("id")
        b64 = encode_media(media_bytes, media_type)
        
        payload = {
            "id": job_id,
            "generation": b64,
            "state": "ok",
            "seed": int(job.get("payload", {}).get("seed", 0)),
            "media_type": media_type
        }
        
        # Debug: log payload details (without the large base64)
        logger.info(f"DEBUG payload: id={job_id}, seed={payload['seed']}, media_type={media_type}, b64_len={len(b64)}")
        
        # Add video-specific parameters if needed
        if media_type == "video":
            original_filename = self._ensure_mp4_extension(filename, job_id)
            payload.update({
                "filename": original_filename,
                "form": "video",
                "type": "video"
            })
        
        return payload
    
    def _ensure_mp4_extension(self, filename: str, job_id: str) -> str:
        if not filename:
            return f"video_{job_id}.mp4"
        if not filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
            return f"{filename}.mp4"
        return filename

