# Gateway Provider System

## Architecture
The provider system enables multi-AI-provider support with load balancing and failover.

## Core Components

### BaseProvider (`app/providers/base.py`)
Abstract base class defining the provider interface:
- `chat_completion(payload, traceparent)` - Non-streaming request
- `stream_chat(payload, traceparent)` - Streaming with async generator
- `health_check(timeout)` - Health status check
- Accepts shared `httpx.AsyncClient` for connection pooling

### ProviderFactory (`app/providers/factory.py`)
Factory pattern for creating provider instances:
- `create_provider(provider_type)` - Create specific provider
- `create_primary_provider()` - Get highest priority provider
- `get_fallback_providers()` - Get backup providers sorted by priority
- Loads config from environment variables (DEEPSEEK_API_KEY, OPENAI_API_KEY)
- Singleton instance: `get_provider_factory()`

### LoadBalancer (`app/providers/loadbalancer.py`)
Distributes requests across multiple providers:
- **Strategies**:
  - `round_robin` - Cycle through providers
  - `weighted` - Random selection weighted by priority
  - `health_first` - Only use healthy providers
- `register_provider(provider, name, weight)` - Add provider
- `get_provider()` - Get next provider based on strategy
- Singleton instance: `get_load_balancer()`

### ProviderHealthChecker (`app/providers/health.py`)
Background health checking for all providers:
- Checks all providers every 30 seconds (configurable)
- Tracks health status in memory
- `mark_unhealthy(name)` - Immediately mark provider as failed
- `is_healthy(name)` - Check health status
- Auto-starts on application startup

### Retry Policy (`app/providers/retry.py`)
Exponential backoff retry decorator:
- Default: 3 retries with exponential backoff
- Configurable max_retries, base_delay, max_delay
- Used via `@BaseProvider.with_retry()` decorator

## Provider Implementations

### DeepSeekProvider (`app/providers/deepseek.py`)
- Base URL: `https://api.deepseek.com/v1`
- Compatible with OpenAI API format
- Supports streaming responses

### OpenAIProvider (`app/providers/openai.py`)
- Base URL: `https://api.openai.com/v1`
- OpenAI organization support
- Supports streaming responses

### MockProvider (`app/providers/mock.py`)
- Testing provider that returns fixed responses
- No network calls
- Useful for testing without API keys

## Configuration
Environment variables:
```
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_PRIORITY=1
DEEPSEEK_ENABLED=true

OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_PRIORITY=2

TEACHPROXY_MOCK_PROVIDER=true  # Force mock mode
```

## Usage Example
```python
from gateway.app.providers.factory import get_load_balancer

lb = get_load_balancer(http_client)  # Uses shared HTTP client
provider = await lb.get_provider()   # Selects based on strategy
response = await provider.chat_completion(payload)
```

## Failover Flow
1. Try primary provider from load balancer
2. On HTTP error/timeout/mark unhealthy, try next provider
3. Repeat up to `MAX_FAILOVER_ATTEMPTS` times
4. Return 503 if all providers fail
