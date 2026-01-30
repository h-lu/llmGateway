import os
from datetime import date
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Connection pool settings - optimized for high concurrency
    # Context7 Best Practice: max_overflow=-1 allows unlimited connections under burst load
    db_pool_size: int = 50           # Base pool size
    db_max_overflow: int = -1        # -1 = unlimited overflow (critical for 200+ concurrency)
    db_pool_timeout: int = 5         # Aggressive timeout to fail fast and retry
    db_pool_recycle: int = 1800      # Recycle every 30 minutes (was 1 hour)
    db_pool_pre_ping: bool = True    # Re-enable to detect stale connections
    
    # asyncpg specific optimizations
    db_command_timeout: float = 30.0           # Reduced from 60s for faster timeout
    db_max_prepared_statements: int = 1000     # Prepared statement cache
    
    # Rate limiting - increased for stress testing
    rate_limit_requests_per_minute: int = 10000
    rate_limit_burst_size: int = 2000          # Increased burst capacity

    @property
    def database_url(self) -> str:
        """Build PostgreSQL connection URL."""
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
    semester_start_date: Optional[date] = None  # e.g., "2026-02-17" for Spring 2026
    semester_weeks: int = 16  # Total weeks in a semester
    
    # Provider settings
    default_provider: str = "deepseek"  # deepseek | openai
    
    # OpenAI settings (optional, for multi-provider support)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_organization: Optional[str] = None
    
    # Rate limiting settings
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    rate_limit_window_seconds: int = 60
    rate_limit_fail_closed: bool = False  # If True, deny requests when Redis is unavailable
    
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
    cors_origins: list[str] = ["*"]  # Allowed CORS origins

    @field_validator('rate_limit_requests_per_minute', 'rate_limit_burst_size')
    @classmethod
    def validate_rate_limit_positive(cls, v: int) -> int:
        """Validate rate limit values are positive."""
        if v < 1:
            raise ValueError("Rate limit values must be at least 1")
        return v

    @field_validator('db_pool_size')
    @classmethod
    def validate_pool_size_positive(cls, v: int) -> int:
        """Validate pool_size is positive."""
        if v < 1:
            raise ValueError("db_pool_size must be at least 1")
        return v

    @field_validator('db_max_overflow')
    @classmethod
    def validate_max_overflow(cls, v: int) -> int:
        """Validate max_overflow is -1 (unlimited) or positive."""
        if v < -1:
            raise ValueError("db_max_overflow must be -1 (unlimited) or >= 0")
        return v

    @field_validator('httpx_timeout', 'httpx_connect_timeout', 'httpx_read_timeout')
    @classmethod
    def validate_timeout_positive(cls, v: float) -> float:
        """Validate timeout values are positive."""
        if v <= 0:
            raise ValueError("Timeout values must be positive")
        return v

    @field_validator('quota_sync_interval_seconds')
    @classmethod
    def validate_sync_interval(cls, v: int) -> int:
        """Validate quota sync interval is reasonable."""
        if v < 10:
            raise ValueError("quota_sync_interval_seconds should be at least 10 seconds")
        if v > 3600:
            raise ValueError("quota_sync_interval_seconds should not exceed 1 hour")
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global settings instance
settings = Settings()
