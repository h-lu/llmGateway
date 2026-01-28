"""Conversation database operations."""
from datetime import datetime

from gateway.app.db.models import Conversation
from gateway.app.db.session import get_session


def save_conversation(
    student_id: str,
    prompt: str,
    response: str,
    tokens_used: int,
    action: str,
    rule_triggered: str | None,
    week_number: int,
) -> Conversation:
    """Save a conversation record to the database."""
    with get_session() as session:
        conversation = Conversation(
            student_id=student_id,
            timestamp=datetime.now(),
            prompt_text=prompt,
            response_text=response,
            tokens_used=tokens_used,
            rule_triggered=rule_triggered,
            action_taken=action,
            week_number=week_number,
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        # Detach from session
        session.expunge(conversation)
        return conversation
