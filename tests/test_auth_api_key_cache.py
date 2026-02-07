from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.app.db.models import Student
from gateway.app.middleware import auth as auth_module


pytestmark = pytest.mark.asyncio


async def test_api_key_cache_preserves_provider_fields() -> None:
    # Reset cache between tests to avoid cross-test coupling.
    auth_module._api_key_cache.clear()

    token_hash = "test-hash"
    student = Student(
        id="student-1",
        name="Student",
        email="student@example.com",
        api_key_hash="hash",
        created_at=datetime.now(timezone.utc),
        current_week_quota=100,
        used_quota=1,
        provider_api_key_encrypted="encrypted-key",
        provider_type="openrouter",
    )

    await auth_module._cache_student(token_hash, student)
    cached = await auth_module._get_cached_student(token_hash)

    assert cached is not None
    assert cached.provider_api_key_encrypted == "encrypted-key"
    assert cached.provider_type == "openrouter"

