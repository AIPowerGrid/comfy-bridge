from comfy_bridge.utils import generate_seed, encode_image
from PIL import Image
import io
import base64


def test_generate_seed_with_valid():
    assert isinstance(generate_seed(123), int)


def test_generate_seed_random():
    val = generate_seed(None)
    assert isinstance(val, int)


def test_encode_image():
    data = b"abc"
    assert encode_image(data) == "YWJj"


def test_generate_seed_integer_and_string():
    assert generate_seed(123) == 123
    assert generate_seed("456") == 456


def test_generate_seed_none_and_invalid():
    # None -> nonzero int
    s1 = generate_seed(None)
    assert isinstance(s1, int) and s1 != 0
    # invalid string -> nonzero int
    s2 = generate_seed("nope")
    assert isinstance(s2, int) and s2 != 0


def test_encode_image_round_trip(tmp_path):
    # create a tiny 2×2 red image
    img = Image.new("RGB", (2, 2), (255, 0, 0))
    path = tmp_path / "r.png"
    img.save(path, format="PNG")

    b64 = encode_image(str(path))
    assert isinstance(b64, str) and len(b64) > 0

    data = base64.b64decode(b64)
    img2 = Image.open(io.BytesIO(data))
    assert img2.size == (2, 2)
    assert img2.mode == "RGB"
