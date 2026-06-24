import pytest

from bridge.ws_worker import resolve_output_seeds


def test_resolve_output_seeds_preserves_explicit_seed():
    assert resolve_output_seeds({"seed": 0}, 3) == [0, 1, 2]
    assert resolve_output_seeds({"seed": "42"}, 2) == [42, 43]


def test_resolve_output_seeds_preserves_seed_list():
    assert resolve_output_seeds({"seed": 9, "seeds": [5, "6"]}, 2) == [5, 6]


def test_resolve_output_seeds_rejects_invalid_seed():
    with pytest.raises(ValueError):
        resolve_output_seeds({"seed": -1}, 1)
