from fastapi.testclient import TestClient

from gateway.app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    # Enhanced health check has status and components
    assert "status" in data
    assert "components" in data
    # Should have database, cache, and providers components
    assert "database" in data["components"]
    assert "cache" in data["components"]
    assert "providers" in data["components"]
