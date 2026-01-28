"""Chat API endpoints for the gateway."""

import json
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.app.core.config import settings
from gateway.app.core.http_client import get_http_client
from gateway.app.core.logging import get_logger
from gateway.app.core.tokenizer import TokenCounter, count_message_tokens
from gateway.app.core.utils import get_current_week_number
from gateway.app.db.crud import check_and_consume_quota
from gateway.app.db.models import Student
from gateway.app.exceptions import QuotaExceededError
from gateway.app.middleware.auth import require_api_key
from gateway.app.middleware.request_id import get_request_id
from gateway.app.providers.base import BaseProvider
from gateway.app.providers.factory import get_provider_factory
from gateway.app.services.rules import evaluate_prompt
from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
    get_async_logger,
)

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
    estimated_tokens: int = 1000
) -> int:
    """Check if student has remaining quota and reserve estimated tokens.
    
    Uses atomic check-and-consume to prevent race conditions.
    
    Args:
        student: The student to check
        week_number: Current week number
        estimated_tokens: Estimated tokens to reserve
        
    Returns:
        Remaining token quota after reservation
        
    Raises:
        QuotaExceededError: If student has no remaining quota
    """
    success, remaining, used = await check_and_consume_quota(student.id, estimated_tokens)
    
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
    """
    token_counter = TokenCounter(model=model)
    
    async def stream_generator():
        full_content = ""
        prompt_tokens = count_message_tokens(payload.get("messages", []), model)
        completion_tokens = 0
        
        try:
            async for line in provider.stream_chat(payload):
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
                            
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse SSE line: {line[:100]}")
                except Exception as e:
                    logger.warning(f"Error processing stream chunk: {e}")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"Upstream HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            yield f"data: {{\"error\": \"Upstream error: {e.response.status_code}\"}}\n\n"
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {{\"error\": \"Stream error: {str(e)}\"}}\n\n"
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
                    "request_id": request_id
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
        upstream_response = await provider.chat_completion(payload)
        
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
):
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
            response=result.message,
            tokens_used=0,
            action="blocked",
            rule_triggered=result.rule_id,
            week_number=week_number,
            max_tokens=0,
            request_id=request_id,
        )
        async_logger.log_conversation(background_tasks, log_data)
        
        return JSONResponse(
            content=create_blocked_response(result.message, result.rule_id),
            headers={"X-Request-ID": request_id}
        )
    
    # Check and reserve quota
    await check_and_reserve_quota(student, week_number, estimated_tokens=max_tokens)
    
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
    
    # Initialize provider
    try:
        http_client = get_http_client()
        factory = get_provider_factory(http_client)
        provider = factory.create_primary_provider()
    except RuntimeError as e:
        logger.error(f"Provider initialization failed: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "AI provider not configured"
            }
        )
    
    # Handle streaming vs non-streaming
    if stream:
        return await handle_streaming_response(
            provider, payload, student, prompt, result,
            week_number, max_tokens, request_id, model,
            background_tasks, async_logger
        )
    else:
        return await handle_non_streaming_response(
            provider, payload, student, prompt, result,
            week_number, max_tokens, request_id, model,
            background_tasks, async_logger
        )
