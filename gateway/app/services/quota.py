from dataclasses import dataclass
from datetime import datetime


@dataclass
class QuotaState:
    week_number: int
    free_tokens: int
    used_tokens: int


def apply_usage(state: QuotaState, used_tokens: int, now: datetime) -> QuotaState:
    return QuotaState(
        week_number=state.week_number,
        free_tokens=state.free_tokens,
        used_tokens=state.used_tokens + used_tokens,
    )
