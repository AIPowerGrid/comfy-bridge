from comfy_bridge.utils import generate_seed, encode_image


def test_generate_seed_with_valid():
    assert isinstance(generate_seed(123), int)


def test_generate_seed_random():
    val = generate_seed(None)
    assert isinstance(val, int)


def test_encode_image():
    data = b"abc"
    assert encode_image(data) == "YWJj"