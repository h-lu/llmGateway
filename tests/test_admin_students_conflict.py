from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from gateway.app.main import app
from gateway.app.middleware.auth import get_admin_token


def _clear_admin_token_cache() -> None:
    if hasattr(get_admin_token, "_cached_token"):
        delattr(get_admin_token, "_cached_token")


def test_admin_create_student_returns_409_on_duplicate_email(monkeypatch) -> None:
    _clear_admin_token_cache()
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")

    from gateway.app.api.admin import students as students_api

    def _raise_integrity_error(*args, **kwargs):
        raise IntegrityError(statement=None, params=None, orig=Exception("unique"))

    monkeypatch.setattr(students_api, "create_student", _raise_integrity_error)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/admin/students",
        headers={"Authorization": "Bearer test-admin-token"},
        json={"name": "Alice", "email": "alice@example.com", "quota": 123},
    )

    assert resp.status_code == 409, resp.text
    assert "Email" in resp.json().get("detail", "")

    _clear_admin_token_cache()

