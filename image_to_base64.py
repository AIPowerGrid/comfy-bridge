#!/usr/bin/env python3
"""
Utility script to convert an image file to base64 format for I2V testing.
"""

import base64
import sys
from pathlib import Path

def image_to_base64(image_path):
    """Convert an image file to base64 string."""
    try:
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            base64_string = base64.b64encode(image_data).decode('utf-8')
            return base64_string
    except Exception as e:
        print(f"Error converting image: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python image_to_base64.py <image_path>")
        print("Example: python image_to_base64.py my_image.png")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    
    if not image_path.exists():
        print(f"Error: Image file '{image_path}' not found")
        sys.exit(1)
    
    print(f"Converting '{image_path}' to base64...")
    
    base64_data = image_to_base64(image_path)
    
    if base64_data:
        print(f"\nBase64 encoded image:")
        print(f"Length: {len(base64_data)} characters")
        print(f"First 100 chars: {base64_data[:100]}...")
        
        # Save to file
        output_file = image_path.stem + "_base64.txt"
        with open(output_file, 'w') as f:
            f.write(base64_data)
        
        print(f"\nFull base64 data saved to: {output_file}")
        
        # Show example payload
        print(f"\nExample I2V job payload:")
        print(f'{{')
        print(f'  "input_image": "{base64_data[:50]}...",')
        print(f'  "input_image_filename": "{image_path.name}",')
        print(f'  "prompt": "Your animation prompt here",')
        print(f'  "video_frames": 81,')
        print(f'  "frame_rate": 16')
        print(f'}}')
    else:
        print("Failed to convert image")
        sys.exit(1)

if __name__ == "__main__":
    main() 