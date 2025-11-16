from typing import Any, Union
import base64
import random
import os
from pathlib import Path


def generate_seed(provided: Any) -> int:
    try:
        v = int(provided)
        return v if v > 0 else random.randint(1, 2**32 - 1)
    except Exception:
        return random.randint(1, 2**32 - 1)


def encode_media(data: Union[str, bytes, Path], media_type: str = "media") -> str:
    if isinstance(data, (bytes, bytearray)):
        raw = data
    else:
        try:
            path = Path(data)
            if not path.exists():
                raise FileNotFoundError(f"{media_type} file not found: {path}")
            raw = path.read_bytes()
        except Exception as e:
            raise ValueError(f"Unable to read {media_type} file '{data}': {e}")
    return base64.b64encode(raw).decode()


def encode_image(data: Union[str, bytes]) -> str:
    return encode_media(data, "image")


def encode_video(data: Union[str, bytes]) -> str:
    return encode_media(data, "video")
