# Gateway Provider System

## Overview
The provider system implements a multi-provider architecture with health checking, load balancing, and failover capabilities.

## Base Provider (`app/providers/base.py`)

### BaseProvider Class
Abstract base class for all providers.

**Key Methods:**
- `chat_completion()`: Non-streaming chat completion
- `stream_chat()`: Streaming chat completion
- `health_check()`: Provider health verification
- `with_retry()`: Retry logic wrapper

**Dependencies:**
- Uses shared httpx HTTP client from `app/core/http_client.py`
- Automatic retry with exponential backoff via `app/providers/retry.py`

## Provider Factory (`app/providers/factory.py`)

### ProviderFactory Class
Manages provider creation and configuration.

**Key Methods:**
- `create_provider()`: Instantiate provider by type
- `create_primary_provider()`: Get main provider
- `get_fallback_providers()`: Get backup providers for failover
- `is_provider_configured()`: Check if provider has valid credentials

### Provider Types
- `deepseek`: DeepSeek API provider
- `openai`: OpenAI API provider
- `mock`: Mock provider for testing

### Module Functions
- `get_provider_factory()`: Get singleton factory instance
- `get_health_checker()`: Get health checker instance
- `get_load_balancer()`: Get load balancer instance

## Load Balancer (`app/providers/loadbalancer.py`)

### LoadBalanceStrategy Enum
- `ROUND_ROBIN`: Distribute requests evenly
- `WEIGHTED`: Weighted distribution based on configured weights
- `HEALTH_FIRST`: Prioritize healthy providers

### LoadBalancer Class
**Key Methods:**
- `register_provider()`: Add a provider to the pool
- `unregister_provider()`: Remove a provider
- `get_provider()`: Get next provider based on strategy
- `get_available_providers()`: Get all non-unavailable providers
- `get_healthy_providers()`: Get only healthy providers

## Health Checker (`app/providers/health.py`)

### HealthChecker Class
Monitors provider health with periodic checks.

**Key Features:**
- Configurable check interval
- Tracks consecutive failures
- Marks providers as unhealthy after threshold
- Auto-recovery when provider responds

## Provider Implementations

### OpenAI Provider (`app/providers/openai.py`)
Implements OpenAI-compatible API with:
- Standard chat completions endpoint
- Streaming support
- API key authentication

### DeepSeek Provider (`app/providers/deepseek.py`)
Implements DeepSeek API with:
- Compatible with OpenAI format
- Custom base URL support

### Mock Provider (`app/providers/mock.py`)
For testing and development:
- Returns predefined responses
- No external API calls
- Configurable delay simulation

## Retry Logic (`app/providers/retry.py`)

Exponential backoff retry mechanism:
- Configurable max attempts
- Increasing delays between retries
- Jitter for thundering herd prevention
