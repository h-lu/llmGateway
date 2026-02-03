"""Chat API endpoints for the gateway."""

import json
from typing import Any, Dict, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.app.core.config import settings
from gateway.app.core.http_client import get_http_client
from gateway.app.core.logging import get_logger
from gateway.app.core.tokenizer import TokenCounter, count_message_tokens
from gateway.app.core.utils import get_current_week_number
from gateway.app.db.models import Student
from gateway.app.exceptions import QuotaExceededError
from gateway.app.middleware.auth import require_api_key
from gateway.app.middleware.request_id import get_request_id, get_traceparent
from gateway.app.providers.base import BaseProvider
from gateway.app.providers.factory import get_load_balancer
from gateway.app.providers.loadbalancer import LoadBalancer
from gateway.app.services.rule_service import evaluate_prompt_async
from gateway.app.services.weekly_prompt_service import (
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
)
from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
    get_async_logger,
)
from gateway.app.services.request_router import get_request_router
from gateway.app.services.quota_cache import get_quota_cache_service

# Import extracted modules
from gateway.app.api.chat_quota import check_student_quota, check_and_reserve_quota
from gateway.app.api.chat_responses import (
    create_blocked_response,
    handle_streaming_response,
    handle_non_streaming_response,
)

# Maximum failover attempts for provider failures (from configuration)
MAX_FAILOVER_ATTEMPTS = settings.max_failover_attempts


class ChatMessage(BaseModel):
    """Message in a chat conversation."""
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Request model for chat completions with validation."""
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str = Field(default=settings.default_provider, min_length=1)
    max_tokens: int = Field(default=2048, ge=1, le=32000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    
    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        """Ensure messages list is not empty after validation."""
        if not v:
            raise ValueError("messages array cannot be empty")
        return v


def get_load_balancer_dependency() -> LoadBalancer:
    """Get the load balancer instance as a FastAPI dependency.
    
    Returns:
        LoadBalancer instance with all configured providers
    """
    try:
        http_client = get_http_client()
        return get_load_balancer(http_client)
    except RuntimeError:
        # HTTP client not initialized, let get_load_balancer handle it
        return get_load_balancer(None)


router = APIRouter()
logger = get_logger(__name__)


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request, 
    background_tasks: BackgroundTasks,
    student: Student = Depends(require_api_key),
    async_logger: AsyncConversationLogger = Depends(get_async_logger),
    load_balancer: LoadBalancer = Depends(get_load_balancer_dependency),
) -> StreamingResponse | JSONResponse:
    """Handle chat completion requests with request routing.
    
    This endpoint uses a RequestRouter to separate streaming and non-streaming
    requests into different concurrency pools:
    - Streaming: Limited to 50 concurrent connections
    - Normal: Allows 200 concurrent requests (fast, high priority)
    
    This separation ensures fast non-streaming requests are not blocked by
    long-running streaming connections, improving P50 latency.
    
    This endpoint:
    1. Validates the API key and checks quota
    2. Evaluates the prompt against rules
    3. Forwards to the AI provider (with fallback support)
    4. Saves the conversation and updates quota (async via background tasks)
    
    Note: Database session is managed internally to ensure streaming responses
    do not hold connections for extended periods.
    
    Args:
        request: The incoming request
        background_tasks: FastAPI background tasks for async logging
        student: Authenticated student (from API key)
        async_logger: Async conversation logger instance
        
    Returns:
        StreamingResponse for streaming requests, or JSON response otherwise
        
    Raises:
        HTTPException: Various status codes for different error conditions
    """
    request_id = get_request_id(request)
    
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    
    # Validate request using Pydantic model
    try:
        chat_request = ChatRequest(**body)
    except Exception as validation_error:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": str(validation_error)
            }
        )
    
    # Extract validated values
    messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    prompt = messages[-1]["content"] if messages else ""
    model = chat_request.model
    max_tokens = chat_request.max_tokens
    temperature = chat_request.temperature
    stream = chat_request.stream
    
    # Request Router: Acquire slot based on request type
    # This separates streaming and normal requests for better P50 latency
    request_router = get_request_router()
    slot_acquired = False
    
    if stream:
        acquired = await request_router.acquire_streaming_slot()
        slot_type = "streaming"
    else:
        acquired = await request_router.acquire_normal_slot()
        slot_type = "normal"
    
    if not acquired:
        logger.warning(
            f"Request rejected: {slot_type} capacity exceeded",
            extra={
                "student_id": student.id,
                "request_id": request_id,
                "slot_type": slot_type
            }
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "capacity_exceeded",
                "message": f"{slot_type.capitalize()} request capacity exceeded. Please retry later."
            }
        )
    
    # Track slot for release in finally block
    slot_acquired = True
    
    try:
        # Evaluate against rule engine
        week_number = get_current_week_number()
        result = await evaluate_prompt_async(prompt, week_number=week_number)
    except Exception as e:
        logger.warning(f"Rule evaluation failed: {e}", extra={"request_id": request_id})
        # Continue without rule evaluation
        result = None
    
    if result and result.action == "blocked":
        logger.info(
            "Request blocked by rule",
            extra={
                "student_id": student.id,
                "rule_id": result.rule_id,
                "request_id": request_id
            }
        )
        
        # Schedule blocked conversation saving as background task
        log_data = ConversationLogData(
            student_id=student.id,
            prompt=prompt,
            response=result.message or "",
            tokens_used=0,
            action="blocked",
            rule_triggered=result.rule_id,
            week_number=week_number,
            max_tokens=0,
            request_id=request_id,
        )
        async_logger.log_conversation(background_tasks, log_data)
        
        return JSONResponse(
            content=create_blocked_response(result.message or "", result.rule_id),
            headers={"X-Request-ID": request_id}
        )
    
    # Load and inject weekly system prompt
    # Use a separate session that will be closed before streaming
    from gateway.app.db.async_session import get_async_session
    async with get_async_session() as db_session:
        weekly_prompt_service = get_weekly_prompt_service()
        weekly_prompt = await weekly_prompt_service.get_prompt_for_week(db_session, week_number)
        modified_messages = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        if weekly_prompt:
            logger.info(
                "Weekly system prompt injected",
                extra={
                    "student_id": student.id,
                    "week_number": week_number,
                    "prompt_id": weekly_prompt.id,
                    "request_id": request_id,
                }
            )
        
        # Check and reserve quota within the same session
        # Session will be committed and closed before streaming starts
        remaining = await check_and_reserve_quota(
            student, week_number, estimated_tokens=max_tokens, session=db_session
        )
        
        # Commit the quota reservation before closing session
        await db_session.commit()
    
    # Session is now closed - streaming response won't hold database connection
    
    # Build payload for upstream
    payload = {
        "model": model,
        "messages": modified_messages,  # Use modified messages with weekly prompt
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    
    # Note: Guide action is deprecated in favor of weekly system prompts
    # Keep for backward compatibility but log a warning
    if result.action == "guided":
        logger.warning(
            "Guide action is deprecated, use weekly system prompts instead",
            extra={
                "student_id": student.id,
                "rule_id": result.rule_id,
                "request_id": request_id
            }
        )
        # Still apply the guide for backward compatibility
        guidance_system = {"role": "system", "content": f"[学习引导] {result.message}"}
        payload["messages"] = [guidance_system] + modified_messages
    
    # Initialize provider with load balancer and failover support
    last_error = None
    
    try:
        for attempt in range(MAX_FAILOVER_ATTEMPTS):
            try:
                provider = await load_balancer.get_provider()
                provider_name = getattr(provider, '__class__', None)
                if provider_name:
                    provider_name = provider_name.__name__
                else:
                    provider_name = "unknown"
                
                logger.info(
                    f"Provider selected",
                    extra={
                        "request_id": request_id,
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "strategy": load_balancer.strategy.value
                    }
                )
                
                # Get traceparent for distributed tracing
                traceparent = get_traceparent(request)
                
                # Handle streaming vs non-streaming
                if stream:
                    return await handle_streaming_response(
                        provider, payload, student, prompt, result,
                        week_number, max_tokens, request_id, model,
                        background_tasks, async_logger, traceparent
                    )
                else:
                    return await handle_non_streaming_response(
                        provider, payload, student, prompt, result,
                        week_number, max_tokens, request_id, model,
                        background_tasks, async_logger, traceparent
                    )
                    
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"Provider failed on attempt {attempt + 1}, trying failover",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                # Mark provider as unhealthy for immediate failover
                try:
                    provider_name = getattr(provider, '__class__', None)
                    if provider_name:
                        provider_name = provider_name.__name__.lower().replace('provider', '')
                        load_balancer._health_checker.mark_unhealthy(provider_name)
                except Exception as mark_error:
                    # Log but don't fail if marking unhealthy fails
                    logger.debug(
                        f"Failed to mark provider unhealthy: {mark_error}",
                        extra={"request_id": request_id}
                    )
                continue
            except RuntimeError as e:
                # No providers available - distinguish between unconfigured and unhealthy
                error_msg = str(e)
                logger.error(f"No providers available: {e}", extra={"request_id": request_id})
                
                if "No providers registered" in error_msg:
                    detail = {
                        "error": "service_unavailable",
                        "message": "AI provider not configured. Please check provider settings."
                    }
                elif "No healthy providers" in error_msg:
                    detail = {
                        "error": "service_unavailable",
                        "message": "All AI providers are currently unhealthy. Please try again later."
                    }
                else:
                    detail = {
                        "error": "service_unavailable",
                        "message": "AI service temporarily unavailable. Please try again later."
                    }
                raise HTTPException(status_code=503, detail=detail)
        
        # All failover attempts exhausted
        logger.error(
            f"All providers failed after {MAX_FAILOVER_ATTEMPTS} attempts",
            extra={
                "request_id": request_id,
                "last_error": str(last_error),
                "error_type": type(last_error).__name__ if last_error else None
            }
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "All AI providers are unavailable. Please try again later."
            }
        )
    
    except HTTPException as e:
        # Release reserved quota on provider failure
        if e.status_code == 503:
            quota_service = get_quota_cache_service()
            # Create a new session for quota release (streaming session is already closed)
            async with get_async_session() as release_session:
                released = await quota_service.release_quota(
                    student.id, max_tokens, week_number, release_session
                )
                await release_session.commit()
            if released:
                logger.info(
                    f"Released {max_tokens} reserved tokens after provider failure",
                    extra={"request_id": request_id, "student_id": student.id}
                )
        raise
    
    finally:
        # Release the request router slot
        if slot_acquired:
            if stream:
                request_router.release_streaming_slot()
            else:
                request_router.release_normal_slot()
