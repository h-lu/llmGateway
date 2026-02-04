"""
Tests for Admin API endpoints
"""
import pytest
import time
from fastapi.testclient import TestClient
from gateway.app.main import app

client = TestClient(app)
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class TestDashboardAPI:
    """Tests for dashboard endpoints"""

    def test_dashboard_stats(self, monkeypatch, auth_headers):
        """Test dashboard stats endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)  # Small delay to avoid rate limit
        response = client.get("/admin/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "students" in data
        assert "conversations" in data
        assert "rules" in data
        assert "blocked" in data

    def test_dashboard_activity(self, monkeypatch, auth_headers):
        """Test dashboard activity endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/dashboard/activity?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_dashboard_stats_unauthorized(self, monkeypatch):
        """Test dashboard stats without auth fails"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/dashboard/stats")
        assert response.status_code == 401


class TestStudentsAPI:
    """Tests for students endpoints"""

    def test_list_students(self, monkeypatch, auth_headers):
        """Test list students endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/students", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestConversationsAPI:
    """Tests for conversations endpoints"""

    def test_list_conversations(self, monkeypatch, auth_headers):
        """Test list conversations endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/conversations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_list_conversations_with_filter(self, monkeypatch, auth_headers):
        """Test list conversations with action filter"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/conversations?action=blocked", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestRulesAPI:
    """Tests for rules endpoints"""

    def test_list_rules(self, monkeypatch, auth_headers):
        """Test list rules endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/rules", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_reload_rules_cache(self, monkeypatch, auth_headers):
        """Test reload rules cache endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.post("/admin/rules/reload-cache", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


class TestWeeklyPromptsAPI:
    """Tests for weekly prompts endpoints"""

    def test_list_prompts(self, monkeypatch, auth_headers):
        """Test list weekly prompts endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/weekly-prompts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_current_prompt(self, monkeypatch, auth_headers):
        """Test get current week prompt endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/weekly-prompts/current", headers=auth_headers)
        assert response.status_code == 200
        # May return null if no prompt set

    def test_get_prompt_by_week(self, monkeypatch, auth_headers):
        """Test get prompt by week number endpoint"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/weekly-prompts/week/1", headers=auth_headers)
        assert response.status_code == 200


class TestAdminRouter:
    """Tests for admin router structure"""

    def test_admin_routes_exist(self, monkeypatch):
        """Test that admin routes are registered"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        admin_routes = [r for r in routes if r and r.startswith('/admin')]
        assert len(admin_routes) > 0

    def test_admin_token_required(self, monkeypatch):
        """Test that admin endpoints require token"""
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        time.sleep(0.05)
        response = client.get("/admin/dashboard/stats")
        assert response.status_code == 401
        assert "Invalid or missing admin token" in response.json()["detail"]
