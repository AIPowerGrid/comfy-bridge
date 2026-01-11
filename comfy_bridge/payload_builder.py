import logging
import re
from typing import Dict, Any
from .utils import encode_media
from .config import Settings

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
        
        # For images with R2 upload, use special handling (similar to videos)
        if media_type == "image" and r2_upload_url:
            return self._build_image_r2_payload(
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
            # IMPORTANT: We use the upload URL as-provided in r2_uploads
            # The file is uploaded to the exact path specified in the presigned URL
            # We cannot modify presigned URLs as it invalidates the signature
            # Construct r2_uploads array from the upload URL (as-provided)
            # The API expects an array of upload info objects
            r2_uploads = [{"url": r2_upload_url}]
        
        payload = {
            "id": job_id,
            "state": "ok",
            "seed": int(job.get("payload", {}).get("seed", 0)),
            "filename": original_filename,
            "form": "video",
            "type": "video",
            "media_type": "video",
            "file_size": len(media_bytes)  # File size in bytes
        }
        
        # Include wallet address if provided in the job (for payment attribution)
        # API now uses wallet_address instead of wallet
        # Fallback to WALLET_ADDRESS from .env if job doesn't have one
        wallet_address = job.get("wallet_address") or job.get("wallet") or Settings.WALLET_ADDRESS
        if wallet_address:
            payload["wallet_address"] = wallet_address
            logger.debug(f"Including wallet_address in payload: {wallet_address[:10]}..." if len(wallet_address) > 10 else f"Including wallet_address: {wallet_address}")
        
        # Include tags if provided in the job
        tags = job.get("tags")
        if tags:
            payload["tags"] = tags
        
        # For videos, construct download URL from upload URL
        # IMPORTANT: The file is uploaded to the exact path in the presigned URL (which may be .webp)
        # We construct the download URL to point to where the video file SHOULD be (.mp4)
        # The API should handle the mapping, or the file should be uploaded to the correct path
        if r2_upload_url:
            # Construct download URL from upload URL by removing query params (signed part)
            # The base URL before the "?" is typically the public access URL
            base_url = r2_upload_url.split("?")[0] if "?" in r2_upload_url else r2_upload_url
            logger.info(f"Video: Processing upload URL - base_url: {base_url}, job_id: {job_id}")
            
            # For videos, use the actual upload path (.webp) as download URL
            # IMPORTANT: Browsers determine video playback based on Content-Type header, not file extension
            # We set Content-Type: video/mp4 when uploading, so browsers will play it correctly
            # even though the URL ends in .webp
            if base_url.endswith('.webp'):
                # Use the actual .webp path where the file is stored
                # Content-Type: video/mp4 header ensures browsers play it as video
                download_url = base_url
                logger.info(f"Video: Using .webp path as download URL: {download_url}")
                logger.info(f"Video: Content-Type header (video/mp4) ensures browsers play it correctly despite .webp extension")
            elif job_id and job_id in base_url:
                # If URL contains job_id but doesn't end in .webp, ensure it has .mp4 extension
                if not base_url.endswith(('.mp4', '.webm', '.avi', '.mov')):
                    download_url = re.sub(r'\.[^.]+$', '', base_url) + '.mp4'
                    logger.info(f"Video: Constructing .mp4 URL from upload URL: {base_url} -> {download_url}")
                else:
                    download_url = base_url
                    logger.info(f"Video: Upload URL already has video extension: {download_url}")
            elif not base_url.endswith(('.mp4', '.webm', '.avi', '.mov')):
                # URL doesn't have a video extension, add .mp4
                download_url = base_url + '.mp4' if not base_url.endswith('.') else base_url + 'mp4'
                logger.info(f"Video: Adding .mp4 extension to URL: {base_url} -> {download_url}")
            else:
                # URL already has a video extension, use as-is
                download_url = base_url
                logger.info(f"Video: Using upload URL as-is (already has video extension): {download_url}")
            
            payload["r2_download_url"] = download_url
            logger.info(f"Video: Final r2_download_url set to: {download_url}")
        else:
            # Fallback: use API-provided r2_download_url if no upload URL
            r2_download = job.get("r2_download") or job.get("r2_download_url")
            if r2_download:
                # Use the API-provided URL as-is (even if it's .webp)
                # The Content-Type header and media_type field will ensure correct handling
                payload["r2_download_url"] = r2_download
                logger.info(f"Video: Using API-provided r2_download_url: {r2_download}")
        
        # Note: For videos, we use .webp path as download URL
        # The Content-Type header (video/mp4) set during upload ensures browsers play it correctly
        # Browsers prioritize Content-Type over file extension for MIME type detection
        if payload.get("r2_download_url") and payload.get("r2_download_url").endswith('.webp'):
            logger.info(f"Video: Using .webp path as download URL - Content-Type header ensures correct playback")
        
        # Include r2_uploads if available
        if r2_uploads:
            payload["r2_uploads"] = r2_uploads
            # When R2 upload is available, include empty generation field (API requires it)
            # This prevents extremely long request bodies/headers
            # The API will fetch the video from R2 using the r2_uploads URLs
            payload["generation"] = ""  # Empty string - API requires field but data is in R2
            logger.info(f"Video: R2 upload available - using empty generation field to avoid large payload")
        else:
            # Fallback: Only include base64 if R2 upload is not available
            logger.warning("No r2_uploads array or r2_upload URL found, using base64 generation only")
            b64 = encode_media(media_bytes, "video")
            b64_size_mb = len(b64) / BYTES_PER_MB
            
            if b64_size_mb > MAX_B64_SIZE_MB:
                logger.warning(f"Base64 video size is {b64_size_mb:.1f}MB - this may cause API errors")
            
            payload["generation"] = b64
        
        # Debug: log payload details (without the large base64)
        logger.info(f"DEBUG submit payload: id={job_id}, seed={payload['seed']}, filename={original_filename}, form={payload.get('form')}, type={payload.get('type')}, media_type={payload.get('media_type')}, file_size={len(media_bytes)}, wallet_address={wallet_address or 'N/A'}, r2_download_url={payload.get('r2_download_url', 'none')}, r2_uploads={'present' if r2_uploads else 'none'}")
        
        return payload
    
    def _build_image_r2_payload(
        self, job: Dict[str, Any], media_bytes: bytes, 
        filename: str, r2_upload_url: str
    ) -> Dict[str, Any]:
        """Build payload for images with R2 upload URL."""
        job_id = job.get("id")
        
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
            "media_type": "image",
            "file_size": len(media_bytes)  # File size in bytes
        }
        
        # Include wallet address if provided in the job (for payment attribution)
        # API now uses wallet_address instead of wallet
        # Fallback to WALLET_ADDRESS from .env if job doesn't have one
        wallet_address = job.get("wallet_address") or job.get("wallet") or Settings.WALLET_ADDRESS
        if wallet_address:
            payload["wallet_address"] = wallet_address
            logger.debug(f"Including wallet_address in payload: {wallet_address[:10]}..." if len(wallet_address) > 10 else f"Including wallet_address: {wallet_address}")
        
        # Include tags if provided in the job
        tags = job.get("tags")
        if tags:
            payload["tags"] = tags
        
        # Include R2 download URL if provided by the API
        r2_download = job.get("r2_download") or job.get("r2_download_url")
        if r2_download:
            payload["r2_download_url"] = r2_download
        elif r2_upload_url:
            # Construct download URL from upload URL by removing query params (signed part)
            # The base URL before the "?" is typically the public access URL
            download_url = r2_upload_url.split("?")[0] if "?" in r2_upload_url else r2_upload_url
            payload["r2_download_url"] = download_url
        
        # Include r2_uploads if available
        b64 = None  # Initialize to avoid UnboundLocalError
        if r2_uploads:
            payload["r2_uploads"] = r2_uploads
            # When R2 upload is available, include empty generation field (API requires it)
            # This prevents extremely long request bodies/headers
            # The API will fetch the image from R2 using the r2_uploads URLs
            payload["generation"] = ""  # Empty string - API requires field but data is in R2
            logger.info(f"Image: R2 upload available - using empty generation field to avoid large payload")
        else:
            # Fallback: Only include base64 if R2 upload is not available
            logger.warning("No r2_uploads array or r2_upload URL found, using base64 generation only")
            b64 = encode_media(media_bytes, "image")
            b64_size_mb = len(b64) / BYTES_PER_MB
            
            if b64_size_mb > MAX_B64_SIZE_MB:
                logger.warning(f"Base64 image size is {b64_size_mb:.1f}MB - this may cause API errors")
            
            payload["generation"] = b64
        
        # Debug: log payload details (without the large base64)
        b64_info = f"b64_len={len(b64)}" if b64 else "b64_len=N/A (R2 upload)"
        logger.info(f"DEBUG payload: id={job_id}, seed={payload['seed']}, media_type=image, file_size={len(media_bytes)}, wallet_address={wallet_address or 'N/A'}, {b64_info}, r2_uploads={'present' if r2_uploads else 'none'}, r2_download_url={payload.get('r2_download_url', 'none')}")
        
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
            "media_type": media_type,
            "file_size": len(media_bytes)  # File size in bytes
        }
        
        # Include wallet address if provided in the job (for payment attribution)
        # API now uses wallet_address instead of wallet
        # Fallback to WALLET_ADDRESS from .env if job doesn't have one
        wallet_address = job.get("wallet_address") or job.get("wallet") or Settings.WALLET_ADDRESS
        if wallet_address:
            payload["wallet_address"] = wallet_address
            logger.debug(f"Including wallet_address in payload: {wallet_address[:10]}..." if len(wallet_address) > 10 else f"Including wallet_address: {wallet_address}")
        
        # Include tags if provided in the job
        tags = job.get("tags")
        if tags:
            payload["tags"] = tags
        
        # Include R2 download URL if provided
        r2_download = job.get("r2_download") or job.get("r2_download_url")
        if r2_download:
            payload["r2_download_url"] = r2_download
        
        # Debug: log payload details (without the large base64)
        logger.info(f"DEBUG payload: id={job_id}, seed={payload['seed']}, media_type={media_type}, file_size={len(media_bytes)}, wallet_address={wallet_address or 'N/A'}, b64_len={len(b64)}")
        
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

