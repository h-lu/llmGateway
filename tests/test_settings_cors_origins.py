import pytest

from gateway.app.core.config import Settings


def test_cors_origins_accepts_host_without_json(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "43.163.94.63")

    settings = Settings(_env_file=None)
    assert "http://43.163.94.63" in settings.cors_origins


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["http://localhost:5173"]', ["http://localhost:5173"]),
        ("*", ["*"]),
        ("[]", []),
        ("", []),
    ],
)
def test_cors_origins_parsing_variants(monkeypatch, raw: str, expected: list[str]) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)

    settings = Settings(_env_file=None)
    assert settings.cors_origins == expected

