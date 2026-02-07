from datetime import datetime, timezone

from fastapi.testclient import TestClient

from gateway.app.db.models import Student
from gateway.app.main import app
from gateway.app.middleware.auth import get_admin_token


def _clear_admin_token_cache() -> None:
    if hasattr(get_admin_token, "_cached_token"):
        delattr(get_admin_token, "_cached_token")


def test_admin_create_student_serializes_student_orm(monkeypatch) -> None:
    _clear_admin_token_cache()
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")

    # Import the module to patch the function reference used by the router.
    from gateway.app.api.admin import students as students_api

    def _fake_create_student(name: str, email: str, quota: int = 10000):
        student = Student(
            id="student-1",
            name=name,
            email=email,
            api_key_hash="hash",
            created_at=datetime.now(timezone.utc),
            current_week_quota=quota,
            used_quota=0,
        )
        return student, "api-key-1"

    monkeypatch.setattr(students_api, "create_student", _fake_create_student)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/admin/students",
        headers={"Authorization": "Bearer test-admin-token"},
        json={"name": "Alice", "email": "alice@example.com", "quota": 123},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"] == "api-key-1"
    assert data["student"]["email"] == "alice@example.com"
    assert data["student"]["current_week_quota"] == 123

    _clear_admin_token_cache()

