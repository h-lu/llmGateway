from datetime import datetime

from gateway.app.services.quota import QuotaState, apply_usage


def test_quota_deducts_usage():
    state = QuotaState(week_number=3, free_tokens=1000, used_tokens=100)
    updated = apply_usage(state, used_tokens=200, now=datetime(2026, 1, 27))
    assert updated.used_tokens == 300
