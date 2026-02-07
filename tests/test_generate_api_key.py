import re


def test_generate_api_key_is_importable_and_urlsafe() -> None:
    from gateway.app.core.security import generate_api_key

    key1 = generate_api_key()
    key2 = generate_api_key()

    assert isinstance(key1, str)
    assert key1
    assert len(key1) <= 512
    assert re.fullmatch(r"[A-Za-z0-9_-]+", key1)

    # Should be unpredictable; collisions are astronomically unlikely.
    assert key1 != key2

