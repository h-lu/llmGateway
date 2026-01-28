"""Custom exceptions for the gateway application."""

from fastapi import HTTPException


class QuotaExceededError(HTTPException):
    """Raised when a student has exceeded their weekly token quota.
    
    Returns HTTP 429 Too Many Requests with details about quota status.
    """
    
    def __init__(
        self,
        remaining: int = 0,
        reset_week: int | None = None,
        detail: str | None = None
    ):
        message = detail or (
            f"Weekly token quota exceeded. "
            f"Remaining: {remaining} tokens. "
        )
        if reset_week:
            message += f"Quota resets at week {reset_week}."
        
        super().__init__(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": message,
                "remaining_tokens": remaining,
                "reset_week": reset_week,
            }
        )


class AuthenticationError(HTTPException):
    """Raised when API key authentication fails."""
    
    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            status_code=401,
            detail={
                "error": "authentication_failed",
                "message": detail,
            }
        )


class RuleViolationError(HTTPException):
    """Raised when a prompt violates a blocking rule."""
    
    def __init__(self, rule_id: str | None = None, message: str = "Content blocked by policy"):
        super().__init__(
            status_code=400,
            detail={
                "error": "rule_violation",
                "message": message,
                "rule_id": rule_id,
            }
        )
