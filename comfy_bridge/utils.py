from typing import Any
import base64
import random


def generate_seed(provided: Any) -> int:
    try:
        v = int(provided)
        return v if v > 0 else random.randint(1, 2**32 - 1)
    except Exception:
        return random.randint(1, 2**32 - 1)


def encode_image(data: bytes) -> str:
    return base64.b64encode(data).decode()