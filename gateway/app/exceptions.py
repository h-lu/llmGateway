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


class QuotaExceededWithGuidanceError(GatewayException):
    """配额不足异常，包含配置指引。
    
    Maps to HTTP 429 Too Many Requests with guidance.
    """
    status_code = 429
    
    def __init__(
        self,
        student_id: str,
        remaining: int,
        reset_week: int,
        message: str,
    ):
        self.student_id = student_id
        self.remaining = remaining
        self.reset_week = reset_week
        self.guidance_message = message
        super().__init__(message)
    
    def to_response(self) -> dict:
        """转换为 API 响应格式"""
        return {
            "error": "quota_exceeded",
            "error_code": "QUOTA_EXCEEDED_CONFIGURE_KEY",
            "message": self.guidance_message,
            "remaining_tokens": self.remaining,
            "reset_week": self.reset_week,
            "actions": [
                {
                    "type": "configure_key",
                    "title": "配置自己的 API Key",
                    "description": "使用自己的 DeepSeek Key 继续学习",
                    "url": "/settings/api-key",
                },
                {
                    "type": "wait",
                    "title": "等待下周",
                    "description": f"配额将在第 {self.reset_week} 周重置",
                }
            ],
            "recommended_provider": {
                "name": "DeepSeek",
                "website": "https://platform.deepseek.com",
                "pricing": "$0.55/$2.19 per 1M tokens",
            }
        }
