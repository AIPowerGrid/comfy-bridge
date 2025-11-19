import logging
import httpx
from typing import Dict, Any
from .config import Settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    def __init__(self, base_url: str = None, timeout: int = 300):
        self.base_url = base_url or Settings.COMFYUI_URL
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
    
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        logger.debug(f"Submitting workflow to ComfyUI ({len(workflow)} nodes)")
        
        resp = await self.client.post("/prompt", json={"prompt": workflow})
        if resp.status_code != 200:
            error_text = resp.text
            logger.error(f"ComfyUI error response (status {resp.status_code}): {error_text}")
            try:
                error_json = resp.json()
                logger.error(f"ComfyUI error JSON: {error_json}")
                # Log node errors if present
                if "node_errors" in error_json:
                    logger.error(f"Node errors: {error_json['node_errors']}")
            except Exception as e:
                logger.error(f"Failed to parse error JSON: {e}")
            resp.raise_for_status()
        response_data = resp.json()
        
        prompt_id = response_data.get("prompt_id")
        if not prompt_id:
            error_msg = response_data.get("error", "No error details")
            node_errors = response_data.get("node_errors", {})
            raise ValueError(
                f"No prompt_id in response. Error: {error_msg}, "
                f"Node errors: {node_errors}"
            )
        
        logger.info(f"Workflow submitted successfully. Prompt ID: {prompt_id}")
        return prompt_id
    
    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        resp = await self.client.get(f"/history/{prompt_id}")
        resp.raise_for_status()
        return resp.json().get(prompt_id, {})
    
    async def get_file(self, filename: str) -> bytes:
        resp = await self.client.get(f"/view?filename={filename}")
        resp.raise_for_status()
        return resp.content
    
    async def get_object_info(self) -> Dict[str, Any]:
        """Fetch object info from ComfyUI to get available models"""
        resp = await self.client.get("/object_info")
        resp.raise_for_status()
        return resp.json()
    
    async def get_available_models(self) -> Dict[str, list]:
        """Get available models organized by loader type"""
        try:
            object_info = await self.get_object_info()
            models = {}
            
            logger.debug(f"Object info keys: {list(object_info.keys())[:10]}...")  # Log first 10 keys
            
            # Get DualCLIPLoader models
            dual_clip = object_info.get("DualCLIPLoader", {})
            if dual_clip:
                clip_inputs = dual_clip.get("input", {})
                required = clip_inputs.get("required", {})
                clip1_config = required.get("clip_name1", [[]])
                clip2_config = required.get("clip_name2", [[]])
                
                clip1 = clip1_config[0] if isinstance(clip1_config, list) and len(clip1_config) > 0 else []
                clip2 = clip2_config[0] if isinstance(clip2_config, list) and len(clip2_config) > 0 else []
                
                if clip1 or clip2:
                    models["DualCLIPLoader"] = {
                        "clip_name1": clip1 if isinstance(clip1, list) else [],
                        "clip_name2": clip2 if isinstance(clip2, list) else []
                    }
                    logger.debug(f"DualCLIPLoader models: clip1={clip1[:3] if isinstance(clip1, list) else clip1}..., clip2={clip2[:3] if isinstance(clip2, list) else clip2}...")
            else:
                logger.debug("DualCLIPLoader not found in object_info")
            
            # Get UNETLoader models
            unet_loader = object_info.get("UNETLoader", {})
            if unet_loader:
                unet_inputs = unet_loader.get("input", {})
                required = unet_inputs.get("required", {})
                unet_config = required.get("unet_name", [[]])
                unet_models = unet_config[0] if isinstance(unet_config, list) and len(unet_config) > 0 else []
                
                if unet_models:
                    models["UNETLoader"] = unet_models if isinstance(unet_models, list) else []
                    logger.debug(f"UNETLoader models: {unet_models[:3] if isinstance(unet_models, list) else unet_models}...")
            else:
                logger.debug("UNETLoader not found in object_info")
            
            # Get VAELoader models
            vae_loader = object_info.get("VAELoader", {})
            if vae_loader:
                vae_inputs = vae_loader.get("input", {})
                required = vae_inputs.get("required", {})
                vae_config = required.get("vae_name", [[]])
                vae_models = vae_config[0] if isinstance(vae_config, list) and len(vae_config) > 0 else []
                
                if vae_models:
                    models["VAELoader"] = vae_models if isinstance(vae_models, list) else []
                    logger.debug(f"VAELoader models: {vae_models[:3] if isinstance(vae_models, list) else vae_models}...")
            else:
                logger.debug("VAELoader not found in object_info")
            
            logger.info(f"Fetched available models: {len(models)} loader types found")
            return models
        except Exception as e:
            logger.error(f"Failed to fetch available models: {e}", exc_info=True)
            return {}
    
    async def close(self):
        await self.client.aclose()

