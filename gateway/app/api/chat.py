"""Chat API endpoints for the gateway."""

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.app.core.config import settings
from gateway.app.core.http_client import get_http_client
from gateway.app.core.logging import get_logger
from gateway.app.core.tokenizer import TokenCounter, count_message_tokens
from gateway.app.core.utils import get_current_week_number
from gateway.app.services.quota_cache import get_quota_cache_service
from gateway.app.db.models import Student
from gateway.app.db.dependencies import SessionDep
from gateway.app.exceptions import QuotaExceededError
from gateway.app.middleware.auth import require_api_key
from gateway.app.middleware.request_id import get_request_id, get_traceparent
from gateway.app.providers.base import BaseProvider
from gateway.app.providers.factory import get_load_balancer
from gateway.app.providers.loadbalancer import LoadBalancer
from gateway.app.services.rule_service import evaluate_prompt
from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
    get_async_logger,
)

# Maximum failover attempts for provider failures (from configuration)
MAX_FAILOVER_ATTEMPTS = settings.max_failover_attempts


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


# Backward compatibility: old function name (sync version for tests)
def check_student_quota(student: Student, week_number: int) -> int:
    """Check if student has remaining quota (backward compatibility).
    
    Args:
        student: The student to check
        week_number: Current week number
        
    Returns:
        Remaining token quota
        
    Raises:
        QuotaExceededError: If student has no remaining quota
    """
    remaining = student.current_week_quota - student.used_quota
    
    if remaining <= 0:
        raise QuotaExceededError(
            remaining=remaining,
            reset_week=week_number + 1,
            detail=f"Weekly token quota exceeded. "
                   f"Quota: {student.current_week_quota}, "
                   f"Used: {student.used_quota}, "
                   f"Remaining: {remaining}"
        )
    
    return remaining


async def check_and_reserve_quota(
    student: Student, 
    week_number: int, 
    estimated_tokens: int = 1000,
    session: SessionDep = None,
) -> int:
    """Check if student has remaining quota and reserve estimated tokens.
    
    First checks cache for quota state, falls back to database on miss
    or insufficient quota. Uses optimistic locking for cache updates.
    
    Args:
        student: The student to check
        week_number: Current week number
        estimated_tokens: Estimated tokens to reserve
        session: Database session for transaction consistency (optional)
        
    Returns:
        Remaining token quota after reservation
        
    Raises:
        QuotaExceededError: If student has no remaining quota
    """
    quota_service = get_quota_cache_service()
    success, remaining, used = await quota_service.check_and_reserve_quota(
        student_id=student.id,
        week_number=week_number,
        current_week_quota=student.current_week_quota,
        tokens_needed=estimated_tokens,
        session=session,
    )
    
    if not success:
        raise QuotaExceededError(
            remaining=remaining,
            reset_week=week_number + 1,
            detail=f"Weekly token quota exceeded. "
                   f"Quota: {student.current_week_quota}, "
                   f"Used: {used}, "
                   f"Remaining: {remaining}"
        )
    
    return remaining


def create_blocked_response(message: str, rule_id: str | None = None) -> Dict[str, Any]:
    """Create a blocked response in OpenAI format.
    
    Args:
        message: The blocking message to return
        rule_id: ID of the rule that was triggered
        
    Returns:
        OpenAI-formatted response dict
    """
    return {
        "id": f"blocked-{rule_id or 'unknown'}",
        "object": "chat.completion",
        "created": int(__import__('time').time()),
        "model": "blocked",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": message},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }


async def handle_streaming_response(
    provider: BaseProvider,
    payload: Dict[str, Any],
    student: Student,
    prompt: str,
    result: Any,
    week_number: int,
    max_tokens: int,
    request_id: str,
    model: str,
    background_tasks: BackgroundTasks,
    async_logger: AsyncConversationLogger,
    traceparent: Optional[str] = None,
) -> StreamingResponse:
    """Handle streaming chat completion response.
    
    Args:
        provider: AI provider instance
        payload: Request payload
        student: Authenticated student
        prompt: Original prompt
        result: Rule evaluation result
        week_number: Current academic week
        max_tokens: Maximum tokens reserved
        request_id: Request ID for tracing
        model: Model name for token counting
        background_tasks: FastAPI background tasks for async logging
        async_logger: Async conversation logger instance
        
    Returns:
        StreamingResponse with SSE stream
        
    Error Handling:
        - JSON decode errors: Logged but stream continues (non-fatal)
        - Upstream errors: Returns error message to client and terminates
        - Unexpected errors: Returns generic error message (no sensitive info)
    """
    token_counter = TokenCounter(model=model)
    
    async def stream_generator():
        full_content = ""
        prompt_tokens = count_message_tokens(payload.get("messages", []), model)
        completion_tokens = 0
        parse_errors = 0  # Track consecutive parse errors
        max_parse_errors = 10  # Abort after too many errors
        
        try:
            async for line in provider.stream_chat(payload, traceparent=traceparent):
                # Check for excessive parse errors
                if parse_errors >= max_parse_errors:
                    logger.error(
                        f"Too many parse errors ({parse_errors}), aborting stream",
                        extra={"request_id": request_id}
                    )
                    yield 'data: {"error": "Stream parsing failed, please retry"}\n\n'
                    yield "data: [DONE]\n\n"
                    return
                
                yield line + "\n\n"
                
                # Parse and count tokens
                try:
                    text_chunk = line.strip()
                    if text_chunk.startswith("data: ") and text_chunk != "data: [DONE]":
                        data_str = text_chunk[6:]
                        data = json.loads(data_str)
                        
                        # Accumulate content for token counting
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            completion_tokens += token_counter.add_text(content)
                        
                        # Use provider-reported usage if available
                        usage = data.get("usage", {})
                        if usage.get("total_tokens"):
                            completion_tokens = usage.get("completion_tokens", completion_tokens)
                        
                        # Reset parse error counter on success
                        parse_errors = 0
                            
                except json.JSONDecodeError:
                    parse_errors += 1
                    # Log at warning level if persistent, debug otherwise
                    log_level = logger.warning if parse_errors > 3 else logger.debug
                    log_level(
                        f"Failed to parse SSE line (error {parse_errors}/{max_parse_errors})",
                        extra={
                            "request_id": request_id,
                            "line_preview": line[:100] if len(line) < 200 else line[:100] + "..."
                        }
                    )
                except (KeyError, IndexError, TypeError) as e:
                    # Data structure errors - log but continue
                    parse_errors += 1
                    logger.warning(
                        f"Unexpected data structure in stream chunk: {e}",
                        extra={"request_id": request_id, "error_type": type(e).__name__}
                    )
                except Exception as e:
                    # Unexpected errors during parsing
                    parse_errors += 1
                    logger.warning(
                        f"Error processing stream chunk: {e}",
                        extra={"request_id": request_id, "error_type": type(e).__name__}
                    )
                    
        except httpx.HTTPStatusError as e:
            # Upstream API error - log details but return safe message
            logger.error(
                f"Upstream HTTP error: {e.response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": e.response.status_code,
                    "response_preview": e.response.text[:200] if len(e.response.text) > 200 else e.response.text
                }
            )
            # Return safe error message (no upstream details to client)
            yield 'data: {"error": "Upstream service error"}\n\n'
            yield "data: [DONE]\n\n"
            return
        except httpx.TimeoutException:
            logger.error(
                "Upstream timeout",
                extra={"request_id": request_id}
            )
            yield 'data: {"error": "Request timeout, please retry"}\n\n'
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            # Unexpected error - log full details but return generic message
            logger.exception(
                f"Unexpected stream error: {e}",
                extra={"request_id": request_id}
            )
            # Generic error message (no exception details to client)
            yield 'data: {"error": "Stream interrupted, please retry"}\n\n'
            yield "data: [DONE]\n\n"
            return
        finally:
            # Calculate total tokens
            total_tokens = prompt_tokens + completion_tokens
            
            logger.info(
                "Stream completed",
                extra={
                    "student_id": student.id,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "request_id": request_id,
                    "parse_errors": parse_errors
                }
            )
            
            # Schedule conversation saving as background task
            log_data = ConversationLogData(
                student_id=student.id,
                prompt=prompt,
                response=full_content,
                tokens_used=total_tokens,
                action=result.action,
                rule_triggered=result.rule_id,
                week_number=week_number,
                max_tokens=max_tokens,
                request_id=request_id,
            )
            async_logger.log_conversation(background_tasks, log_data)
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"X-Request-ID": request_id}
    )


async def handle_non_streaming_response(
    provider: BaseProvider,
    payload: Dict[str, Any],
    student: Student,
    prompt: str,
    result: Any,
    week_number: int,
    max_tokens: int,
    request_id: str,
    model: str,
    background_tasks: BackgroundTasks,
    async_logger: AsyncConversationLogger,
    traceparent: Optional[str] = None,
) -> JSONResponse:
    """Handle non-streaming chat completion response.
    
    Args:
        provider: AI provider instance
        payload: Request payload
        student: Authenticated student
        prompt: Original prompt
        result: Rule evaluation result
        week_number: Current academic week
        max_tokens: Maximum tokens reserved
        request_id: Request ID for tracing
        model: Model name for token counting
        background_tasks: FastAPI background tasks for async logging
        async_logger: Async conversation logger instance
        
    Returns:
        JSONResponse with completion
    """
    try:
        upstream_response = await provider.chat_completion(payload, traceparent=traceparent)
        
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Upstream HTTP error: {e.response.status_code}",
            extra={
                "status_code": e.response.status_code,
                "response": e.response.text[:500],
                "request_id": request_id
            }
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "message": f"Upstream provider returned {e.response.status_code}",
                "provider_status": e.response.status_code
            }
        )
    except httpx.TimeoutException:
        logger.error("Upstream timeout", extra={"request_id": request_id})
        raise HTTPException(
            status_code=504,
            detail={
                "error": "upstream_timeout",
                "message": "Upstream provider timeout"
            }
        )
    except Exception as e:
        logger.error(f"Upstream error: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "message": f"Failed to communicate with upstream: {str(e)}"
            }
        )
    
    # Extract response content and tokens
    response_content = ""
    if upstream_response.get("choices"):
        response_content = upstream_response["choices"][0].get("message", {}).get("content", "")
    
    # Use reported usage or calculate
    usage = upstream_response.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    
    if not total_tokens and response_content:
        # Calculate tokens if not provided by provider
        prompt_tokens = count_message_tokens(payload.get("messages", []), model)
        completion_tokens = count_message_tokens([{"role": "assistant", "content": response_content}], model)
        total_tokens = prompt_tokens + completion_tokens
        upstream_response["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
    
    # Schedule conversation saving as background task
    log_data = ConversationLogData(
        student_id=student.id,
        prompt=prompt,
        response=response_content,
        tokens_used=total_tokens,
        action=result.action,
        rule_triggered=result.rule_id,
        week_number=week_number,
        max_tokens=max_tokens,
        request_id=request_id,
    )
    async_logger.log_conversation(background_tasks, log_data)
    
    # Add request ID to response
    return JSONResponse(
        content=upstream_response,
        headers={"X-Request-ID": request_id}
    )


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request, 
    background_tasks: BackgroundTasks,
    student: Student = Depends(require_api_key),
    async_logger: AsyncConversationLogger = Depends(get_async_logger),
    load_balancer: LoadBalancer = Depends(get_load_balancer_dependency),
    session: SessionDep = None,
) -> StreamingResponse | JSONResponse:
    """Handle chat completion requests.
    
    This endpoint:
    1. Validates the API key and checks quota
    2. Evaluates the prompt against rules
    3. Forwards to the AI provider (with fallback support)
    4. Saves the conversation and updates quota (async via background tasks)
    
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
    
    messages: List[Dict[str, str]] = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Messages array is required")
    
    prompt = messages[-1].get("content", "") if messages else ""
    
    # Get configuration from request
    model = body.get("model", settings.default_provider)
    max_tokens = body.get("max_tokens", 2048)
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)
    
    # Evaluate against rule engine
    week_number = get_current_week_number()
    result = evaluate_prompt(prompt, week_number=week_number)
    
    if result.action == "blocked":
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
    
    # Check and reserve quota (pass session for transaction consistency)
    await check_and_reserve_quota(student, week_number, estimated_tokens=max_tokens, session=session)
    
    # Build payload for upstream
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    
    # For guided action, prepend guidance in system message
    if result.action == "guided":
        guidance_system = {"role": "system", "content": f"[学习引导] {result.message}"}
        payload["messages"] = [guidance_system] + list(messages)
        logger.info(
            "Guidance applied",
            extra={
                "student_id": student.id,
                "rule_id": result.rule_id,
                "request_id": request_id
            }
        )
    
    # Initialize provider with load balancer and failover support
    last_error = None
    
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
            except Exception:
                pass  # Ignore errors from health check marking
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
