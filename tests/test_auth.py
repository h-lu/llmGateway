from fastapi.testclient import TestClient

from gateway.app.main import app


def test_auth_missing_key_returns_401():
    client = TestClient(app)
    resp = client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 401
