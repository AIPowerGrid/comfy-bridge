import json
import logging
import httpx
from typing import Dict, Any
from .config import Settings
from .workflow import convert_native_workflow_to_simple

logger = logging.getLogger(__name__)


class ComfyUIClient:
    def __init__(self, base_url: str = None, timeout: int = 300):
        self.base_url = base_url or Settings.COMFYUI_URL
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
    
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        # Validate workflow structure before submission
        try:
            self._validate_workflow_structure(workflow)
        except ValueError as e:
            logger.error(f"Workflow validation failed: {e}")
            # Log the workflow structure for debugging
            if isinstance(workflow, dict) and "nodes" in workflow:
                nodes = workflow.get("nodes", [])
                logger.error(f"Workflow has {len(nodes)} nodes")
                for i, node in enumerate(nodes[:5]):  # Log first 5 nodes
                    logger.error(f"Node {i}: id={node.get('id')}, type={node.get('type')}")
            raise
        
        # Convert ComfyUI native format to simple format if needed
        workflow = self._convert_workflow_format(workflow)
        
        node_count = len(workflow) if isinstance(workflow, dict) and "nodes" not in workflow else len(workflow.get("nodes", []))
        logger.debug(f"Submitting workflow to ComfyUI ({node_count} nodes)")
        
        # Additional validation: check for any '#id' strings in the JSON
        workflow_str = json.dumps(workflow)
        if '"#id"' in workflow_str or "'#id'" in workflow_str:
            logger.error("Found '#id' string in workflow JSON - this will cause ComfyUI errors")
            logger.error(f"Workflow snippet: {workflow_str[:500]}")
            raise ValueError("Workflow contains invalid '#id' placeholder - this indicates a workflow processing error")
        
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
    
    def _validate_workflow_structure(self, workflow: Dict[str, Any]) -> None:
        """Validate workflow structure and ensure all nodes have required properties"""
        # Handle ComfyUI native format (has "nodes" array)
        if isinstance(workflow, dict) and "nodes" in workflow:
            nodes = workflow.get("nodes", [])
            valid_node_ids = set()
            
            # First pass: collect all valid node IDs
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = node.get("id")
                if node_id is not None:
                    valid_node_ids.add(node_id)
                    valid_node_ids.add(str(node_id))
            
            # Second pass: validate nodes
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                node_id = node.get("id")
                node_type = node.get("type")
                
                # Check for invalid node IDs
                if node_id == "#id" or str(node_id) == "#id":
                    raise ValueError(f"Invalid node ID found: '#id'. Node must have a valid numeric ID.")
                
                # Ensure node has type/class_type
                if not node_type:
                    raise ValueError(f"Node {node_id} is missing 'type' property (class_type)")
                
                # Validate node connections/links don't reference invalid nodes
                inputs = node.get("inputs", [])
                if isinstance(inputs, list):
                    for input_item in inputs:
                        if isinstance(input_item, dict):
                            link = input_item.get("link")
                            if link is not None and (link == "#id" or str(link) == "#id"):
                                raise ValueError(f"Node {node_id} has invalid link reference '#id'")
                        elif isinstance(input_item, list) and len(input_item) > 0:
                            ref_id = input_item[0]
                            if ref_id == "#id" or str(ref_id) == "#id":
                                raise ValueError(f"Node {node_id} has invalid node reference '#id' in inputs")
            
            # Validate links array
            links = workflow.get("links", [])
            for link in links:
                if isinstance(link, list) and len(link) >= 2:
                    # Link format: [link_id, from_node, from_slot, to_node, to_slot, type]
                    from_node = link[1] if len(link) > 1 else None
                    to_node = link[3] if len(link) > 3 else None
                    
                    if from_node == "#id" or str(from_node) == "#id":
                        raise ValueError(f"Link {link[0] if len(link) > 0 else 'unknown'} has invalid from_node '#id'")
                    if to_node == "#id" or str(to_node) == "#id":
                        raise ValueError(f"Link {link[0] if len(link) > 0 else 'unknown'} has invalid to_node '#id'")
                    
                    # Check if referenced nodes exist
                    if from_node is not None and from_node not in valid_node_ids and str(from_node) not in valid_node_ids:
                        logger.warning(f"Link references non-existent from_node {from_node}")
                    if to_node is not None and to_node not in valid_node_ids and str(to_node) not in valid_node_ids:
                        logger.warning(f"Link references non-existent to_node {to_node}")
        
        # Handle simple format (direct node objects)
        else:
            for node_id, node_data in workflow.items():
                if not isinstance(node_data, dict):
                    continue
                
                # Check for invalid node IDs
                if node_id == "#id" or str(node_id) == "#id":
                    raise ValueError(f"Invalid node ID found: '#id'. Node must have a valid ID.")
                
                # Ensure node has class_type
                if not node_data.get("class_type"):
                    raise ValueError(f"Node {node_id} is missing 'class_type' property")
    
    def _convert_workflow_format(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ComfyUI native format to simple format if needed, or return as-is"""
        if isinstance(workflow, dict) and "nodes" in workflow:
            converted = convert_native_workflow_to_simple(workflow)
            logger.debug(f"Converted native workflow to simple format with {len(converted)} nodes")
            return converted
        return workflow
    
    async def close(self):
        await self.client.aclose()

