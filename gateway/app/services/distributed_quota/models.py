"""Data models for distributed quota management."""

from dataclasses import dataclass, field


@dataclass
class DistributedQuotaState:
    """Quota state for distributed quota management.
    
    Attributes:
        student_id: The student ID
        current_week_quota: Maximum tokens allowed for the week
        used_quota: Tokens already used (from Redis or DB)
        week_number: The academic week number
        source: Where the data came from ('redis', 'db', or 'cache')
    """
    student_id: str
    current_week_quota: int
    used_quota: int
    week_number: int = field(default=0)
    source: str = field(default="db")
    
    @property
    def remaining(self) -> int:
        """Calculate remaining quota."""
        return self.current_week_quota - self.used_quota
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "student_id": self.student_id,
            "current_week_quota": self.current_week_quota,
            "used_quota": self.used_quota,
            "week_number": self.week_number,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DistributedQuotaState":
        """Create from dictionary."""
        return cls(
            student_id=data["student_id"],
            current_week_quota=data["current_week_quota"],
            used_quota=data["used_quota"],
            week_number=data.get("week_number", 0),
            source=data.get("source", "db"),
        )
