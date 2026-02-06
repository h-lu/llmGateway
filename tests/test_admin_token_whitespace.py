from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from gateway.app.middleware.auth import get_admin_token, require_admin


def _clear_admin_token_cache() -> None:
    if hasattr(get_admin_token, "_cached_token"):
        delattr(get_admin_token, "_cached_token")


def test_get_admin_token_trims_whitespace(monkeypatch):
    _clear_admin_token_cache()
    monkeypatch.setenv("ADMIN_TOKEN", "  token-with-whitespace  \n")

    token = get_admin_token()

    assert token == "token-with-whitespace"
    _clear_admin_token_cache()


def test_require_admin_accepts_trimmed_env_token(monkeypatch):
    _clear_admin_token_cache()
    monkeypatch.setenv("ADMIN_TOKEN", "token-with-newline\n")

    app = FastAPI()

    @app.get("/protected")
    async def protected(_admin=Depends(require_admin)):
        return {"ok": True}

    client = TestClient(app)
    response = client.get(
        "/protected", headers={"Authorization": "Bearer token-with-newline"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    _clear_admin_token_cache()
