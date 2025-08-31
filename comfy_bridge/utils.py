from typing import Any, Union
import base64
import random
import os


def generate_seed(provided: Any) -> int:
    try:
        v = int(provided)
        return v if v > 0 else random.randint(1, 2**32 - 1)
    except Exception:
        return random.randint(1, 2**32 - 1)


def encode_image(data: Union[str, bytes]) -> str:
    if isinstance(data, (bytes, bytearray)):
        raw = data
    else:
        try:
            with open(data, "rb") as f:
                raw = f.read()
        except Exception as e:
            raise ValueError(f"Unable to read image file '{data}': {e}")
    return base64.b64encode(raw).decode()


def encode_video(data: Union[str, bytes]) -> str:
    """Encode video file or bytes to base64 string"""
    if isinstance(data, (bytes, bytearray)):
        raw = data
    else:
        try:
            with open(data, "rb") as f:
                raw = f.read()
        except Exception as e:
            raise ValueError(f"Unable to read video file '{data}': {e}")
    return base64.b64encode(raw).decode()
