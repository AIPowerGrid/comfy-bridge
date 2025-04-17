#!/usr/bin/env python3
"""
ComfyUI Workflow Connection Checker

This script checks the connections in a ComfyUI workflow to verify that the positive and negative
prompts are correctly connected to the KSampler node.
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_connections")

def analyze_workflow(workflow_path: str) -> None:
    """Analyze a workflow file to check connections."""
    logger.info(f"Analyzing workflow: {workflow_path}")
    
    try:
        with open(workflow_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {workflow_path}: {e}")
        return
    except FileNotFoundError:
        logger.error(f"File not found: {workflow_path}")
        return
    
    # Determine workflow format
    if isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list):
        logger.info("Detected ComfyUI web interface format (nodes array)")
        analyze_web_format(data)
    elif isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], dict):
        logger.info("Detected full ComfyUI export format (nodes object)")
        # Not implemented
        logger.warning("Analysis for full ComfyUI export format not implemented")
    elif isinstance(data, dict):
        logger.info("Detected API format (node dictionary)")
        analyze_api_format(data)
    else:
        logger.error(f"Unknown workflow format")

def analyze_api_format(workflow: Dict[str, Any]) -> None:
    """Analyze API format workflow (node dictionary)."""
    # Find KSampler node
    ksampler_node = None
    ksampler_id = None
    
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            ksampler_node = node
            ksampler_id = node_id
            logger.info(f"Found KSampler node: {node_id}")
            break
    
    if not ksampler_node:
        logger.error("No KSampler node found in workflow")
        return
    
    # Check connections
    if "inputs" not in ksampler_node:
        logger.error("KSampler node has no inputs")
        return
    
    positive_connection = None
    negative_connection = None
    
    if "positive" in ksampler_node["inputs"]:
        positive_connection = ksampler_node["inputs"]["positive"]
        if isinstance(positive_connection, list) and len(positive_connection) >= 1:
            logger.info(f"Positive prompt connected to node: {positive_connection[0]}")
        else:
            logger.error(f"Invalid positive prompt connection: {positive_connection}")
            positive_connection = None
    else:
        logger.error("KSampler missing positive prompt connection")
    
    if "negative" in ksampler_node["inputs"]:
        negative_connection = ksampler_node["inputs"]["negative"]
        if isinstance(negative_connection, list) and len(negative_connection) >= 1:
            logger.info(f"Negative prompt connected to node: {negative_connection[0]}")
        else:
            logger.error(f"Invalid negative prompt connection: {negative_connection}")
            negative_connection = None
    else:
        logger.error("KSampler missing negative prompt connection")
    
    # Check the actual text nodes
    if positive_connection:
        positive_node_id = positive_connection[0]
        if positive_node_id in workflow:
            positive_node = workflow[positive_node_id]
            if positive_node.get("class_type") == "CLIPTextEncode":
                if "inputs" in positive_node and "text" in positive_node["inputs"]:
                    text = positive_node["inputs"]["text"]
                    logger.info(f"Positive prompt node text: '{text}'")
                    
                    # Check for placeholders
                    if "POSITIVE_PROMPT_PLACEHOLDER" in text:
                        logger.info("✅ Positive prompt node has correct placeholder")
                    elif "NEGATIVE_PROMPT_PLACEHOLDER" in text:
                        logger.error("❌ PROBLEM: Positive prompt node has NEGATIVE placeholder!")
                    else:
                        logger.warning("⚠️ Positive prompt node has no placeholder")
                else:
                    logger.error("Positive prompt node missing text input")
            else:
                logger.error(f"Node {positive_node_id} is not a CLIPTextEncode node: {positive_node.get('class_type')}")
        else:
            logger.error(f"Positive node ID {positive_node_id} not found in workflow")
    
    if negative_connection:
        negative_node_id = negative_connection[0]
        if negative_node_id in workflow:
            negative_node = workflow[negative_node_id]
            if negative_node.get("class_type") == "CLIPTextEncode":
                if "inputs" in negative_node and "text" in negative_node["inputs"]:
                    text = negative_node["inputs"]["text"]
                    logger.info(f"Negative prompt node text: '{text}'")
                    
                    # Check for placeholders
                    if "NEGATIVE_PROMPT_PLACEHOLDER" in text:
                        logger.info("✅ Negative prompt node has correct placeholder")
                    elif "POSITIVE_PROMPT_PLACEHOLDER" in text:
                        logger.error("❌ PROBLEM: Negative prompt node has POSITIVE placeholder!")
                    else:
                        logger.warning("⚠️ Negative prompt node has no placeholder")
                else:
                    logger.error("Negative prompt node missing text input")
            else:
                logger.error(f"Node {negative_node_id} is not a CLIPTextEncode node: {negative_node.get('class_type')}")
        else:
            logger.error(f"Negative node ID {negative_node_id} not found in workflow")

def analyze_web_format(workflow: Dict[str, Any]) -> None:
    """Analyze web format workflow (nodes array and links array)."""
    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])
    
    # Find KSampler node
    ksampler_node = None
    ksampler_id = None
    
    for node in nodes:
        if isinstance(node, dict) and node.get("type") == "KSampler":
            ksampler_node = node
            ksampler_id = node.get("id")
            logger.info(f"Found KSampler node: {ksampler_id}")
            break
    
    if not ksampler_node:
        logger.error("No KSampler node found in workflow")
        return
    
    # Map the connections using the links
    positive_node = None
    negative_node = None
    
    # Find inputs for positive and negative prompt
    positive_slot = None
    negative_slot = None
    
    if "inputs" in ksampler_node:
        for input_info in ksampler_node["inputs"]:
            if input_info.get("name") == "positive":
                positive_slot = input_info.get("slot_index")
                logger.info(f"Positive prompt connects to slot {positive_slot}")
            elif input_info.get("name") == "negative":
                negative_slot = input_info.get("slot_index")
                logger.info(f"Negative prompt connects to slot {negative_slot}")
    
    if positive_slot is None or negative_slot is None:
        logger.error("Could not determine positive or negative slots")
        return
    
    # Now find the links connecting to those slots
    for link in links:
        if len(link) >= 6:  # Format: [link_id, src_node_id, src_slot, dst_node_id, dst_slot, type]
            dst_node_id = link[3]
            dst_slot = link[4]
            src_node_id = link[1]
            
            if dst_node_id == ksampler_id:
                if dst_slot == positive_slot:
                    logger.info(f"Found positive prompt from node {src_node_id}")
                    # Find that node
                    for node in nodes:
                        if node.get("id") == src_node_id:
                            positive_node = node
                            break
                elif dst_slot == negative_slot:
                    logger.info(f"Found negative prompt from node {src_node_id}")
                    # Find that node
                    for node in nodes:
                        if node.get("id") == src_node_id:
                            negative_node = node
                            break
    
    # Check the text in those nodes
    if positive_node:
        if positive_node.get("type") == "CLIPTextEncode":
            if "widgets_values" in positive_node and len(positive_node["widgets_values"]) > 0:
                text = positive_node["widgets_values"][0]
                logger.info(f"Positive prompt node text: '{text}'")
                
                # Check for placeholders
                if "POSITIVE_PROMPT_PLACEHOLDER" in text:
                    logger.info("✅ Positive prompt node has correct placeholder")
                elif "NEGATIVE_PROMPT_PLACEHOLDER" in text:
                    logger.error("❌ PROBLEM: Positive prompt node has NEGATIVE placeholder!")
                else:
                    logger.warning("⚠️ Positive prompt node has no placeholder")
            else:
                logger.error("Positive prompt node missing text widget value")
        else:
            logger.error(f"Positive node is not a CLIPTextEncode node: {positive_node.get('type')}")
    else:
        logger.error("Could not find positive prompt node")
    
    if negative_node:
        if negative_node.get("type") == "CLIPTextEncode":
            if "widgets_values" in negative_node and len(negative_node["widgets_values"]) > 0:
                text = negative_node["widgets_values"][0]
                logger.info(f"Negative prompt node text: '{text}'")
                
                # Check for placeholders
                if "NEGATIVE_PROMPT_PLACEHOLDER" in text:
                    logger.info("✅ Negative prompt node has correct placeholder")
                elif "POSITIVE_PROMPT_PLACEHOLDER" in text:
                    logger.error("❌ PROBLEM: Negative prompt node has POSITIVE placeholder!")
                else:
                    logger.warning("⚠️ Negative prompt node has no placeholder")
            else:
                logger.error("Negative prompt node missing text widget value")
        else:
            logger.error(f"Negative node is not a CLIPTextEncode node: {negative_node.get('type')}")
    else:
        logger.error("Could not find negative prompt node")

def fix_workflow(workflow_path: str) -> None:
    """Fix a workflow by ensuring prompts go to the right nodes."""
    logger.info(f"Fixing workflow: {workflow_path}")
    
    try:
        with open(workflow_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        return
    
    # For API format
    if isinstance(data, dict) and "nodes" not in data:
        # Find KSampler node
        ksampler_node = None
        ksampler_id = None
        
        for node_id, node in data.items():
            if isinstance(node, dict) and node.get("class_type") == "KSampler":
                ksampler_node = node
                ksampler_id = node_id
                break
        
        if ksampler_node and "inputs" in ksampler_node:
            if "positive" in ksampler_node["inputs"] and "negative" in ksampler_node["inputs"]:
                # Swap positive and negative connections
                temp = ksampler_node["inputs"]["positive"]
                ksampler_node["inputs"]["positive"] = ksampler_node["inputs"]["negative"]
                ksampler_node["inputs"]["negative"] = temp
                logger.info(f"Swapped positive and negative connections in KSampler node {ksampler_id}")
                
                # Save fixed workflow
                fixed_path = str(workflow_path) + ".swapped.json"
                with open(fixed_path, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Saved fixed workflow to {fixed_path}")
                return True
    
    # For web format
    elif isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list):
        # This would require more complex logic to rewrite links in web format
        logger.error("Fixing web format workflows not implemented - export to API format first")
    
    logger.warning("No fixes applied to workflow")
    return False

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        workflows_dir = os.path.join(os.getcwd(), "workflows")
        logger.info(f"No path specified, checking all workflows in: {workflows_dir}")
        
        if os.path.isdir(workflows_dir):
            for filename in os.listdir(workflows_dir):
                if filename.endswith(".json"):
                    workflow_path = os.path.join(workflows_dir, filename)
                    analyze_workflow(workflow_path)
                    print("-" * 80)
        else:
            logger.error(f"Workflows directory not found: {workflows_dir}")
            print("Usage: python check_connections.py [workflow_file.json]")
    else:
        path = sys.argv[1]
        
        if os.path.isfile(path):
            analyze_workflow(path)
            
            # If there's a --fix argument, try to fix the workflow
            if len(sys.argv) > 2 and sys.argv[2] == "--fix":
                fix_workflow(path)
        else:
            logger.error(f"File not found: {path}")

if __name__ == "__main__":
    main() 