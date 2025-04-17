#!/usr/bin/env python3
"""
Prepare ComfyUI Bridge for Release

This script prepares the ComfyUI Bridge codebase for release by:
1. Removing test and debug files
2. Setting correct permissions
3. Creating necessary directories
"""

import os
import shutil
import glob
import stat

def clean_test_files():
    """Remove test and debug files."""
    files_to_remove = [
        # Test files
        "test_*.py",
        "debug_*.py",
        "debug_*.json",
        "test_*.json",
        "bridge_fix.py",
        "bridge_updated.py",
        "fix_workflow.py",
        "horde_bridge.log",
        "run_horde_worker.py",
        
        # Cache files
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        
        # Development files
        ".env.test",
        ".env.example",
        "test_output/",
    ]
    
    for pattern in files_to_remove:
        for path in glob.glob(pattern):
            if os.path.isdir(path):
                print(f"Removing directory: {path}")
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                print(f"Removing file: {path}")
                os.remove(path)

def set_permissions():
    """Set correct permissions for executable scripts."""
    executable_files = [
        "start_bridge.py",
        "prepare_release.py",
        "setup.py",
        "check_connections.py",
    ]
    
    for filename in executable_files:
        if os.path.exists(filename):
            print(f"Setting executable permissions for: {filename}")
            os.chmod(filename, os.stat(filename).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def create_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        "workflows",
        "logs",
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory)

def create_example_env():
    """Create an example .env file."""
    if not os.path.exists(".env.example") and os.path.exists(".env"):
        print("Creating .env.example from .env")
        with open(".env", "r") as env_file:
            content = env_file.readlines()
        
        # Remove any API keys
        with open(".env.example", "w") as example_file:
            for line in content:
                if "API_KEY=" in line:
                    key_part = line.split("=")[0]
                    example_file.write(f"{key_part}=your_api_key_here\n")
                else:
                    example_file.write(line)

def main():
    """Main function."""
    print("Preparing ComfyUI Bridge for release...")
    
    # Create example .env before cleaning
    create_example_env()
    
    # Clean files
    clean_test_files()
    
    # Set permissions
    set_permissions()
    
    # Create directories
    create_directories()
    
    print("Release preparation complete!")

if __name__ == "__main__":
    main() 