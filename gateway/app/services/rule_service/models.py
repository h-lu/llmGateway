"""Rule service models."""
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class RuleResult:
    """Rule evaluation result."""
    triggered: bool
    action: Optional[Literal["block", "guide"]] = None
    message: Optional[str] = None
    rule_id: Optional[int] = None
    matched_content: Optional[str] = None
