"""Token counting utility using tiktoken.

This module provides accurate token counting for OpenAI-compatible models
using the tiktoken library.
"""

from typing import List, Dict, Any, Optional

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    import logging

    logging.getLogger(__name__).warning(
        "tiktoken not available. Token counting will use approximate character-based estimation. "
        "Install with: pip install tiktoken"
    )

# Default encoding to use if tiktoken is available
DEFAULT_ENCODING = "cl100k_base"  # Used by gpt-4, gpt-3.5-turbo, text-embedding-ada-002

# Fallback: approximate tokens as characters / 4
CHARS_PER_TOKEN_ESTIMATE = 4

# Cache for encodings to avoid repeated creation
_encoding_cache: Dict[str, Any] = {}  # Maps encoding name to tiktoken Encoding instance


def get_encoding(model: Optional[str] = None) -> Optional[Any]:
    """Get tiktoken encoding for the specified model.

    Uses a cache to avoid repeated encoding creation.

    Args:
        model: Model name (optional)

    Returns:
        tiktoken Encoding or None if tiktoken not available
    """
    if not TIKTOKEN_AVAILABLE:
        return None

    # Use cache key: model name or default
    cache_key = model if model else DEFAULT_ENCODING

    # Check cache first
    if cache_key in _encoding_cache:
        return _encoding_cache[cache_key]

    try:
        # Try to get encoding for specific model
        if model:
            encoding = tiktoken.encoding_for_model(model)
        else:
            encoding = tiktoken.get_encoding(DEFAULT_ENCODING)

        # Store in cache
        _encoding_cache[cache_key] = encoding
        return encoding
    except KeyError:
        # Model not found, use default encoding
        encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
        _encoding_cache[cache_key] = encoding
        return encoding


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """Count tokens in the given text.

    Uses tiktoken if available, otherwise falls back to character-based estimation.

    Args:
        text: Text to count tokens for
        model: Model name for encoding selection

    Returns:
        Number of tokens
    """
    if not text:
        return 0

    encoding = get_encoding(model)
    if encoding:
        return len(encoding.encode(text))

    # Fallback estimation
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


def count_message_tokens(
    messages: List[Dict[str, str]], model: Optional[str] = None
) -> int:
    """Count tokens in a list of chat messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name for encoding selection

    Returns:
        Number of tokens
    """
    if not messages:
        return 0

    encoding = get_encoding(model)
    if not encoding:
        # Fallback: count all text content
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += len(content) // CHARS_PER_TOKEN_ESTIMATE
        return total

    # Use tiktoken's message counting (approximation)
    # Every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_message = 3
    tokens_per_name = 1

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>

    return num_tokens


def estimate_response_tokens(
    prompt_tokens: int, max_tokens: Optional[int] = None
) -> int:
    """Estimate total tokens for a response.

    Args:
        prompt_tokens: Number of tokens in the prompt
        max_tokens: Maximum tokens to generate

    Returns:
        Estimated total tokens
    """
    if max_tokens:
        return prompt_tokens + max_tokens

    # Default estimate: response is typically similar size to prompt
    return prompt_tokens * 2


class TokenCounter:
    """Token counter that can be used for streaming responses.

    This class provides efficient incremental token counting for streaming responses
    using tiktoken's encode_ordinary() to count tokens in each chunk individually,
    avoiding memory overhead of storing accumulated text.
    """

    def __init__(self, model: Optional[str] = None):
        """Initialize token counter.

        Args:
            model: Model name for encoding selection
        """
        self.model = model
        self.encoding = get_encoding(model)
        self._token_count = 0

    def add_text(self, text: str) -> int:
        """Add text and return token count for the new text.

        Uses incremental encoding to count tokens in the new text chunk only,
        avoiding the memory overhead of storing accumulated text.

        Note: This is an approximation. Token boundaries at chunk edges may
        cause slight inaccuracies (typically within 1-2 tokens) compared to
        counting the full text at once. This is acceptable for streaming
        quota estimation where exact counts are provided by the provider.

        Args:
            text: Text chunk to add

        Returns:
            Token count for the new text chunk
        """
        if not text:
            return 0

        if self.encoding:
            # Incremental encoding: count tokens in this chunk only
            # Note: encode_ordinary() is used instead of encode() because we don't
            # need special token handling for content text, and it's slightly faster.
            delta = len(self.encoding.encode_ordinary(text))
            self._token_count += delta
            return delta
        else:
            # Fallback: estimate based on character count
            delta = len(text) // CHARS_PER_TOKEN_ESTIMATE
            self._token_count += delta
            return delta

    def get_total(self) -> int:
        """Get total token count."""
        return self._token_count

    def reset(self) -> None:
        """Reset the counter."""
        self._token_count = 0
