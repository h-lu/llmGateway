import os
from datetime import date
import json
import re
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_cors_origins(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = [str(v).strip() for v in raw]
        return [v for v in items if v]

    raw = str(raw).strip()
    if not raw or raw == "[]":
        return []
    if raw == "*":
        return ["*"]

    # Prefer JSON (recommended format), but tolerate non-JSON values to avoid
    # crashing the app on misconfigured deployments.
    if raw.startswith(("[", "{", '"', "'")):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            items = [str(v).strip() for v in parsed]
            return [v for v in items if v]
        if isinstance(parsed, str):
            raw = parsed.strip()
            if not raw or raw == "[]":
                return []
            if raw == "*":
                return ["*"]

    parts = [p for p in re.split(r"[,\s]+", raw) if p]
    origins: list[str] = []
    for part in parts:
        if part == "*":
            return ["*"]
        if "://" in part:
            origins.append(part)
            continue
        # If a host is provided without scheme, support both HTTP and HTTPS
        # origins. Browsers include the scheme in the Origin header.
        origins.append(f"http://{part}")
        origins.append(f"https://{part}")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    result: list[str] = []
    for origin in origins:
        if origin in seen:
            continue
        seen.add(origin)
        result.append(origin)
    return result


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via environment variables or .env file.
    """

    # Debug mode - enables detailed error responses
    debug: bool = False

    # PostgreSQL settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_test_port: int = 5433
    db_user: str = "teachproxy"
    db_password: str = "teachproxy123"
    db_name: str = "teachproxy"
    db_test_name: str = "teachproxy_test"

    # Connection pool settings - aligned with asyncpg best practices
    db_pool_size: int = 100  # Base pool size (SQLAlchemy pool_size)
    db_max_overflow: int = 50  # Overflow connections for burst traffic
    db_pool_timeout: int = 30  # Seconds to wait for connection (increased from 5s)
    db_pool_recycle: int = 300  # Recycle every 5 minutes (reduced from 30min)
    db_pool_pre_ping: bool = True  # Detect stale connections before use

    # SQLite pool settings (file-based SQLite during tests or stress)
    db_sqlite_pool_size: int = 10
    db_sqlite_max_overflow: int = 5

    # asyncpg specific optimizations
    db_command_timeout: float = 30.0  # Per-command timeout in seconds
    db_max_queries: int = 50000  # Recycle connection after 50K queries
    db_max_inactive_connection_lifetime: float = (
        300.0  # Recycle idle connections after 5 minutes
    )
    db_max_cached_statement_lifetime: int = 0  # No limit on prepared statement cache

    # Explicit DATABASE_URL (takes priority over db_* settings)
    database_url_override: str = Field(default="", validation_alias="DATABASE_URL")

    @property
    def database_url(self) -> str:
        """Build database connection URL.

        Priority:
        1. database_url_override (from DATABASE_URL env var or .env file)
        2. Built from db_* settings
        """
        # Check for explicit DATABASE_URL (loaded via pydantic-settings from .env)
        if self.database_url_override:
            # Allow SQLite for stress tests and mock provider mode
            if "sqlite" in self.database_url_override.lower():
                if os.getenv("TEACHPROXY_MOCK_PROVIDER") != "true":
                    raise ValueError(
                        "DATABASE_URL must use PostgreSQL (SQLite only allowed with TEACHPROXY_MOCK_PROVIDER=true)"
                    )
            return self.database_url_override

        # Check if running in pytest
        if os.getenv("PYTEST_CURRENT_TEST"):
            return (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_test_port}/{self.db_test_name}"
            )
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # DeepSeek settings
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # HTTP Client connection pool settings
    httpx_timeout: float = 60.0  # Default timeout for all operations
    httpx_connect_timeout: float = 10.0  # Time to establish connection
    httpx_read_timeout: float = 60.0  # Time to read response data
    httpx_write_timeout: float = 10.0  # Time to send request data
    httpx_pool_timeout: float = 5.0  # Time to acquire connection from pool
    httpx_keepalive_expiry: float = 30.0
    httpx_max_connections: int = 100
    httpx_max_keepalive_connections: int = 20

    # Academic calendar settings
    semester_start_date: date | None = None  # e.g., "2026-02-17" for Spring 2026
    semester_weeks: int = 16  # Total weeks in a semester

    # Provider settings
    default_provider: str = "deepseek"  # deepseek | openai

    # OpenAI settings (optional, for multi-provider support)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_organization: str | None = None

    # Rate limiting settings
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    rate_limit_window_seconds: int = 60
    rate_limit_fail_closed: bool = (
        False  # If True, deny requests when Redis is unavailable
    )

    # Request router settings (overload protection)
    request_router_enabled: bool = True
    request_router_streaming_limit: int = 50
    request_router_normal_limit: int = 200
    request_router_timeout: float = 5.0

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "text"  # text | structured | json

    # Cache settings
    cache_enabled: bool = True
    cache_default_ttl: int = 300  # 5 minutes

    # Redis settings (optional)
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"

    # Distributed quota settings
    quota_sync_interval_seconds: int = 60  # Sync Redis to DB every 60 seconds
    quota_redis_ttl_days: int = 7  # TTL for Redis quota keys (7 days)

    # Provider failover settings
    max_failover_attempts: int = 3  # Maximum failover attempts for provider failures

    # CORS settings
    # Use NoDecode so misconfigured values (e.g. "43.163.94.63") don't crash JSON
    # parsing at startup.
    cors_origins: Annotated[list[str], NoDecode] = ["*"]  # Allowed CORS origins

    @field_validator("cors_origins", mode="before")
    @classmethod
    def decode_cors_origins(cls, v: Any) -> list[str]:
        return _parse_cors_origins(v)

    # LLM Provider settings (Balance Architecture)
    # Teacher Key Pool - DeepSeek Direct (Primary)
    teacher_deepseek_api_key: str = ""
    teacher_deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_direct_timeout: float = 15.0  # 15s timeout for fast failover

    # Teacher Key Pool - OpenRouter (Fallback)
    teacher_openrouter_api_key: str = ""
    teacher_openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: float = 30.0
    openrouter_fallback_models: list[str] = [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
        "anthropic/claude-3-haiku",
    ]

    # LLM Cache settings
    llm_cache_enabled: bool = True
    llm_cache_ttl_concept: int = 3600  # 1 hour for concept questions
    llm_cache_ttl_general: int = 600  # 10 minutes for general
    llm_cache_ttl_short: int = 300  # 5 minutes for short answers
    llm_cache_prefix: str = "teachproxy:v1"
    llm_cache_max_size: int = 10000  # 10KB max cacheable size

    # API Key encryption
    api_key_encryption_key: str = ""  # 32-byte base64 encoded key

    # Student self-registration (optional)
    # If STUDENT_REGISTRATION_CODE is empty, the self-registration endpoint is disabled.
    student_registration_code: str = ""
    student_self_register_default_quota: int = 10000

    # Cost tracking
    cost_tracking_enabled: bool = True

    @field_validator("rate_limit_requests_per_minute", "rate_limit_burst_size")
    @classmethod
    def validate_rate_limit_positive(cls, v: int) -> int:
        """Validate rate limit values are positive."""
        if v < 1:
            raise ValueError("Rate limit values must be at least 1")
        return v

    @field_validator("request_router_streaming_limit", "request_router_normal_limit")
    @classmethod
    def validate_request_router_limits(cls, v: int) -> int:
        """Validate request router limits are positive."""
        if v < 1:
            raise ValueError("request router limits must be at least 1")
        return v

    @field_validator("request_router_timeout")
    @classmethod
    def validate_request_router_timeout(cls, v: float) -> float:
        """Validate request router timeout is positive."""
        if v <= 0:
            raise ValueError("request_router_timeout must be positive")
        return v

    @field_validator(
        "db_pool_size",
        "db_max_overflow",
        "db_sqlite_pool_size",
        "db_sqlite_max_overflow",
    )
    @classmethod
    def validate_pool_size_positive(cls, v: int) -> int:
        """Validate pool_size is positive."""
        if v < 1:
            raise ValueError("pool size values must be at least 1")
        return v

    @field_validator("httpx_timeout", "httpx_connect_timeout", "httpx_read_timeout")
    @classmethod
    def validate_timeout_positive(cls, v: float) -> float:
        """Validate timeout values are positive."""
        if v <= 0:
            raise ValueError("Timeout values must be positive")
        return v

    @field_validator("quota_sync_interval_seconds")
    @classmethod
    def validate_sync_interval(cls, v: int) -> int:
        """Validate quota sync interval is reasonable."""
        if v < 10:
            raise ValueError(
                "quota_sync_interval_seconds should be at least 10 seconds"
            )
        if v > 3600:
            raise ValueError("quota_sync_interval_seconds should not exceed 1 hour")
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global settings instance
settings = Settings()
