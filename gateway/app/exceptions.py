"""Custom exceptions for the gateway application."""


class GatewayException(Exception):
    """Base class for gateway exceptions with HTTP status code.
    
    All custom exceptions should inherit from this class and define
    their specific status_code for consistent HTTP response handling.
    """
    status_code: int = 500
    
    def __init__(self, message: str = "Gateway error"):
        self.message = message
        super().__init__(message)


class QuotaExceededError(GatewayException):
    """Raised when a student has exceeded their weekly token quota.
    
    Exception data includes details about quota status.
    Maps to HTTP 429 Too Many Requests.
    """
    status_code = 429
    
    def __init__(
        self,
        remaining: int = 0,
        reset_week: int | None = None,
        detail: str | None = None
    ):
        self.remaining = remaining
        self.reset_week = reset_week
        message = detail or (
            f"Weekly token quota exceeded. "
            f"Remaining: {remaining} tokens. "
        )
        if reset_week:
            message += f"Quota resets at week {reset_week}."
        super().__init__(message)


class AuthenticationError(GatewayException):
    """Raised when API key authentication fails.
    
    Maps to HTTP 401 Unauthorized.
    """
    status_code = 401
    
    def __init__(self, detail: str = "Invalid or missing API key"):
        self.detail = detail
        super().__init__(detail)


class RuleViolationError(GatewayException):
    """Raised when a prompt violates a blocking rule.
    
    Maps to HTTP 400 Bad Request.
    """
    status_code = 400
    
    def __init__(self, rule_id: str | None = None, message: str = "Content blocked by policy"):
        self.rule_id = rule_id
        self.message = message
        super().__init__(message)
