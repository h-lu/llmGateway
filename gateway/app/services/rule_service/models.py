"""Rule service models."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleResult:
    """Result of evaluating a prompt against rules."""
    action: str  # blocked | guided | passed
    message: Optional[str] = None
    rule_id: Optional[str] = None
