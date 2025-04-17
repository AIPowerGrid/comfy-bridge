"""Model mapper for ComfyUI bridge.

This module maps AI Power Grid model names to local ComfyUI model filenames.
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional


async def get_comfyui_models(comfy_url: str) -> List[str]:
    """Get available models from ComfyUI.
    
    Tries multiple methods to detect available models.
    
    Args:
        comfy_url: URL of the ComfyUI instance
        
    Returns:
        List of available model filenames
    """
    models = []
    
    async with httpx.AsyncClient(base_url=comfy_url, timeout=10) as client:
        # Method 1: Try to get model list from node info
        try:
            response = await client.get("/object_info")
            if response.status_code == 200:
                node_info = response.json()
                if "CheckpointLoaderSimple" in node_info:
                    checkpoint_node = node_info["CheckpointLoaderSimple"]
                    if "input" in checkpoint_node and "required" in checkpoint_node["input"]:
                        for input_name, input_config in checkpoint_node["input"]["required"].items():
                            if input_name == "ckpt_name" and isinstance(input_config, list) and len(input_config) > 0:
                                if isinstance(input_config[0], list):
                                    models.extend(input_config[0])
        except Exception as e:
            print(f"Error getting models from node info: {e}")
        
        # Method 2: Try to get model list from model_list endpoint
        if not models:
            try:
                response = await client.get("/model_list")
                if response.status_code == 200:
                    model_list = response.json()
                    if "checkpoints" in model_list:
                        models.extend(model_list["checkpoints"])
            except Exception as e:
                print(f"Error getting models from model_list endpoint: {e}")
    
    return models

class ModelMapper:
    """Maps between AI Power Grid model names and local ComfyUI model filenames."""
    
    # Common model mapping for reference
    DEFAULT_MODEL_MAP = {
        "stable_diffusion_1.5": "v1-5-pruned-emaonly.safetensors",
        "stable_diffusion_2.1": "v2-1_768-ema-pruned.safetensors",
        "sdxl": "sdxl_base_1.0.safetensors",
        "sdxl turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "SDXL 1.0": "sd_xl_base_1.0.safetensors",
        "sdxl-turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "sd_xl_turbo": "sd_xl_turbo_1.0_fp16.safetensors",
        "juggernaut_xl": "juggernaut_xl.safetensors",
        "playground_v2": "playground_v2.safetensors",
        "dreamshaper_8": "dreamshaper_8.safetensors",
        "stable_diffusion": "v1-5-pruned-emaonly.safetensors"
    }
    
    def __init__(self):
        """Initialize the model mapper."""
        self.available_models: List[str] = []
        self.model_map: Dict[str, str] = {}
        self.default_model: str = ""
    
    async def initialize(self, comfy_url: str):
        """Initialize the model mapper with available models from ComfyUI.
        
        Args:
            comfy_url: URL of the ComfyUI instance
        """
        self.available_models = await get_comfyui_models(comfy_url)
        
        if not self.available_models:
            print("Warning: No models detected in ComfyUI")
            return
        
        # Set default model to the first available model
        self.default_model = self.available_models[0]
        
        # Build a mapping from AI Power Grid model names to local model filenames
        self._build_model_map()
        
        print(f"Initialized model mapper with {len(self.available_models)} models")
        print(f"Default model: {self.default_model}")
    
    def _build_model_map(self):
        """Build the model map based on available models."""
        # Reset the model map
        self.model_map = {}
        
        # Loop through available models and map them to AI Power Grid model names
        for model_filename in self.available_models:
            lower_filename = model_filename.lower()
            
            # Map based on filename patterns
            if "turbo" in lower_filename and "xl" in lower_filename:
                self.model_map["sdxl-turbo"] = model_filename
                self.model_map["sd_xl_turbo"] = model_filename
                self.model_map["SDXL 1.0"] = model_filename
            
            elif "sdxl" in lower_filename or "sd_xl" in lower_filename or "sd-xl" in lower_filename:
                self.model_map["sdxl"] = model_filename
                self.model_map["SDXL 1.0"] = model_filename
            
            elif "v1-5" in lower_filename or "v1.5" in lower_filename or "sd1.5" in lower_filename:
                self.model_map["stable_diffusion_1.5"] = model_filename
                self.model_map["stable_diffusion"] = model_filename
            
            elif "v2-1" in lower_filename or "v2.1" in lower_filename or "sd2.1" in lower_filename:
                self.model_map["stable_diffusion_2.1"] = model_filename
            
            # Map specific model names
            model_name_map = {
                "juggernaut": "juggernaut_xl",
                "playground": "playground_v2",
                "dreamshaper": "dreamshaper_8",
                "deliberate": "deliberate",
                "realistic": "realistic_vision",
                "anything": "anything_v4",
                "openjourney": "openjourney",
                "dreamlike": "dreamlike_diffusion",
                "protogen": "protogen",
            }
            
            for key, value in model_name_map.items():
                if key in lower_filename:
                    self.model_map[value] = model_filename
    
    def get_model_filename(self, horde_model_name: str) -> str:
        """Get the local model filename for an AI Power Grid model name.
        
        Args:
            horde_model_name: AI Power Grid model name
            
        Returns:
            Local model filename
        """
        # If we have a direct mapping, use it
        if horde_model_name in self.model_map:
            return self.model_map[horde_model_name]
        
        # Try to find a partial match
        for horde_name, local_name in self.model_map.items():
            if horde_model_name.lower() in horde_name.lower() or horde_name.lower() in horde_model_name.lower():
                return local_name
        
        # Fall back to the default model
        print(f"Warning: No mapping found for model '{horde_model_name}', using default: {self.default_model}")
        return self.default_model
    
    def get_available_horde_models(self) -> List[str]:
        """Get a list of AI Power Grid model names that can be supported.
        
        Returns:
            List of AI Power Grid model names
        """
        # Return keys from model_map and any default models we might be able to support
        result = list(self.model_map.keys())
        
        # Add default models if we have appropriate local models
        sdxl_keywords = ["xl", "sdxl"]
        sd15_keywords = ["1.5", "v1-5"]
        
        has_sdxl = any(any(kw in m.lower() for kw in sdxl_keywords) for m in self.available_models)
        has_sd15 = any(any(kw in m.lower() for kw in sd15_keywords) for m in self.available_models)
        
        standard_models = []
        if has_sdxl and "sdxl" not in result:
            standard_models.append("sdxl")
        if has_sd15 and "stable_diffusion_1.5" not in result:
            standard_models.append("stable_diffusion_1.5")
            
        # Combine and remove duplicates
        result.extend(standard_models)
        return list(set(result))


# Initialize the model mapper as a singleton
model_mapper = ModelMapper()

async def initialize_model_mapper(comfy_url: str):
    """Initialize the model mapper.
    
    Args:
        comfy_url: URL of the ComfyUI instance
    """
    await model_mapper.initialize(comfy_url)

def get_horde_models() -> List[str]:
    """Get the list of AI Power Grid models that can be supported.
    
    Returns:
        List of model names
    """
    return model_mapper.get_available_horde_models()

def map_model_name(horde_model_name: str) -> str:
    """Map an AI Power Grid model name to a local model filename.
    
    Args:
        horde_model_name: AI Power Grid model name
        
    Returns:
        Local model filename
    """
    return model_mapper.get_model_filename(horde_model_name) 