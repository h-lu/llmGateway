"""Response handling utilities for chat API (streaming and non-streaming)."""

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger
from gateway.app.core.tokenizer import TokenCounter, count_message_tokens
from gateway.app.db.models import Student
from gateway.app.providers.base import BaseProvider
from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
)

logger = get_logger(__name__)


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
        full_content_parts: list[str] = []  # Use list for efficient concatenation
        prompt_tokens = count_message_tokens(payload.get("messages", []), model)
        completion_tokens = 0
        parse_errors = 0  # Track consecutive parse errors
        max_parse_errors = 10  # Abort after too many errors
        
        # Buffer for optimized streaming (reduces syscall overhead)
        buffer: List[str] = []
        buffer_size = 0
        max_buffer_size = 4096  # 4KB buffer for efficient transmission
        
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
                
                # Buffer data for efficient transmission
                buffer.append(line + "\n\n")
                buffer_size += len(line) + 2
                
                # Yield when buffer reaches threshold
                if buffer_size >= max_buffer_size:
                    yield "".join(buffer)
                    buffer = []
                    buffer_size = 0
                
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
                            full_content_parts.append(content)
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
            
            # Stream completed normally - flush remaining buffer
            if buffer:
                yield "".join(buffer)
                buffer = []
                buffer_size = 0
                    
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
            # Flush any remaining buffered data before returning error
            if buffer:
                yield "".join(buffer)
            # Return safe error message (no upstream details to client)
            yield 'data: {"error": "Upstream service error"}\n\n'
            yield "data: [DONE]\n\n"
            return
        except httpx.TimeoutException:
            logger.error(
                "Upstream timeout",
                extra={"request_id": request_id}
            )
            # Flush any remaining buffered data before returning error
            if buffer:
                yield "".join(buffer)
            yield 'data: {"error": "Request timeout, please retry"}\n\n'
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            # Unexpected error - log full details but return generic message
            logger.exception(
                f"Unexpected stream error: {e}",
                extra={"request_id": request_id}
            )
            # Flush any remaining buffered data before returning error
            if buffer:
                yield "".join(buffer)
            # Generic error message (no exception details to client)
            yield 'data: {"error": "Stream interrupted, please retry"}\n\n'
            yield "data: [DONE]\n\n"
            return
        finally:
            # Calculate total tokens
            total_tokens = prompt_tokens + completion_tokens
            
            # Join content parts for logging
            full_content = "".join(full_content_parts) if full_content_parts else ""
            
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
