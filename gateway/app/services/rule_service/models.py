"""Rule service models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleResult:
    """Result of evaluating a prompt against rules."""
    action: str  # blocked | guided | passed
    message: str | None = None
    rule_id: str | None = None
