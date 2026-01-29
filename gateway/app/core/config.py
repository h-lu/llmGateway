from datetime import date
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All settings can be configured via environment variables or .env file.
    """
    
    # Debug mode - enables detailed error responses
    debug: bool = False
    
    # Database settings
    database_url: str = "sqlite+pysqlite:///./teachproxy.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    
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
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global settings instance
settings = Settings()
