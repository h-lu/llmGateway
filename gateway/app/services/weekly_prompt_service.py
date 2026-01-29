"""Weekly system prompt service with caching support.

This service manages weekly system prompt retrieval and injection,
optimized for KV cache efficiency by maintaining consistent prompt
prefixes within the same week.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import WeeklySystemPrompt
from gateway.app.db.weekly_prompt_crud import get_active_prompt_for_week


class WeeklyPromptService:
    """Service for managing weekly system prompts.
    
    Implements in-memory caching for the current week's prompt
    to minimize database queries and maximize consistency.
    
    Cache strategy:
    - Cache the prompt for the current week
    - Invalidate when week number changes
    - Single instance per application (use get_weekly_prompt_service())
    """
    
    def __init__(self):
        self._cached_week: Optional[int] = None
        self._cached_prompt: Optional[WeeklySystemPrompt] = None
    
    async def get_prompt_for_week(
        self,
        session: AsyncSession,
        week_number: int
    ) -> Optional[WeeklySystemPrompt]:
        """Get the system prompt for a specific week.
        
        Uses in-memory caching to avoid repeated DB queries
        for the same week.
        
        Args:
            session: Database session
            week_number: Current week number
            
        Returns:
            WeeklySystemPrompt if configured, None otherwise
        """
        # Check cache
        if self._cached_week == week_number and self._cached_prompt is not None:
            return self._cached_prompt
        
        # Cache miss or week changed - fetch from DB
        prompt = await get_active_prompt_for_week(session, week_number)
        
        # Update cache
        self._cached_week = week_number
        self._cached_prompt = prompt
        
        return prompt
    
    def invalidate_cache(self) -> None:
        """Invalidate the current cache."""
        self._cached_week = None
        self._cached_prompt = None
    
    def reload(self) -> None:
        """Force reload on next request."""
        self.invalidate_cache()


# Global instance
_weekly_prompt_service: Optional[WeeklyPromptService] = None


def get_weekly_prompt_service() -> WeeklyPromptService:
    """Get the global WeeklyPromptService instance (singleton).
    
    Returns:
        WeeklyPromptService singleton instance
    """
    global _weekly_prompt_service
    if _weekly_prompt_service is None:
        _weekly_prompt_service = WeeklyPromptService()
    return _weekly_prompt_service


def reset_weekly_prompt_service() -> None:
    """Reset the global service instance. Useful for testing."""
    global _weekly_prompt_service
    _weekly_prompt_service = None


async def inject_weekly_system_prompt(
    messages: List[Dict[str, Any]],
    weekly_prompt: Optional[WeeklySystemPrompt]
) -> List[Dict[str, Any]]:
    """Inject weekly system prompt into messages.
    
    Replaces any existing system message with the weekly prompt.
    If no system message exists, adds one at the beginning.
    
    This ensures all students in the same week receive identical
    system prompt prefixes, maximizing KV cache efficiency.
    
    Args:
        messages: Original message list
        weekly_prompt: Weekly system prompt to inject, or None to skip
        
    Returns:
        Modified message list with weekly system prompt
    """
    if weekly_prompt is None:
        return messages
    
    # Create new system message from weekly prompt
    system_message = {
        "role": "system",
        "content": weekly_prompt.system_prompt
    }
    
    # Check if first message is already system
    if messages and messages[0].get("role") == "system":
        # Replace existing system message
        new_messages = [system_message] + messages[1:]
    else:
        # Add system message at the beginning
        new_messages = [system_message] + messages
    
    return new_messages


async def get_and_inject_weekly_prompt(
    session: AsyncSession,
    messages: List[Dict[str, Any]],
    week_number: int
) -> List[Dict[str, Any]]:
    """Convenience function: get weekly prompt and inject into messages.
    
    Args:
        session: Database session
        messages: Original message list
        week_number: Current week number
        
    Returns:
        Modified message list with weekly system prompt (if configured)
    """
    service = get_weekly_prompt_service()
    weekly_prompt = await service.get_prompt_for_week(session, week_number)
    return await inject_weekly_system_prompt(messages, weekly_prompt)
