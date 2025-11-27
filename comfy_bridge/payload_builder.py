import logging
from typing import Dict, Any
from .utils import encode_media

logger = logging.getLogger(__name__)


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
        b64 = encode_media(media_bytes, "video")
        r2_uploads = job.get("r2_uploads", [])
        
        payload = {
            "id": job_id,
            "generation": b64,
            "state": "ok",
            "seed": int(job.get("payload", {}).get("seed", 0)),
            "filename": original_filename,
            "form": "video",
            "type": "video",
            "media_type": "video"
        }
        
        if r2_uploads:
            payload["r2_uploads"] = r2_uploads
        
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
        if not filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
            return f"{filename}.mp4" if filename else f"video_{job_id}.mp4"
        return filename if filename else f"video_{job_id}.mp4"

