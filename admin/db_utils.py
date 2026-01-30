"""Database utilities for Streamlit admin panel."""
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from gateway.app.core.config import settings
from gateway.app.db.models import Conversation, QuotaLog, Rule, Student


def get_db_session():
    """Create a database session for admin operations."""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def get_dashboard_stats():
    """Get statistics for dashboard display."""
    session = get_db_session()
    try:
        student_count = session.query(func.count(Student.id)).scalar() or 0
        conversation_count = session.query(func.count(Conversation.id)).scalar() or 0
        rule_count = session.query(func.count(Rule.id)).scalar() or 0
        
        # Blocked conversations count
        blocked_count = session.query(func.count(Conversation.id)).filter(
            Conversation.action_taken == "blocked"
        ).scalar() or 0
        
        # Total tokens used
        total_tokens = session.query(func.sum(Conversation.tokens_used)).scalar() or 0
        
        return {
            "students": student_count,
            "conversations": conversation_count,
            "rules": rule_count,
            "blocked": blocked_count,
            "total_tokens": total_tokens,
        }
    finally:
        session.close()


def get_all_students():
    """Get all students list."""
    session = get_db_session()
    try:
        return session.query(Student).all()
    finally:
        session.close()


def get_all_conversations(limit=100):
    """Get recent conversations."""
    session = get_db_session()
    try:
        return session.query(Conversation).order_by(
            Conversation.timestamp.desc()
        ).limit(limit).all()
    finally:
        session.close()


def get_all_rules():
    """Get all rules."""
    session = get_db_session()
    try:
        return session.query(Rule).all()
    finally:
        session.close()


def get_rule_by_id(rule_id: int):
    """Get a rule by ID."""
    session = get_db_session()
    try:
        return session.query(Rule).filter(Rule.id == rule_id).first()
    finally:
        session.close()


def update_rule(rule_id: int, **kwargs):
    """Update a rule by ID.
    
    Args:
        rule_id: The rule ID to update
        **kwargs: Fields to update (pattern, rule_type, message, active_weeks, enabled)
    
    Returns:
        True if updated successfully, False if rule not found
    """
    session = get_db_session()
    try:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return False
        
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_rule(rule_id: int) -> bool:
    """Delete a rule by ID.
    
    Args:
        rule_id: The rule ID to delete
    
    Returns:
        True if deleted successfully, False if rule not found
    """
    session = get_db_session()
    try:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return False
        
        session.delete(rule)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def toggle_rule_enabled(rule_id: int) -> bool:
    """Toggle the enabled status of a rule.
    
    Args:
        rule_id: The rule ID to toggle
    
    Returns:
        New enabled status (True/False), or None if rule not found
    """
    session = get_db_session()
    try:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return None
        
        rule.enabled = not rule.enabled
        session.commit()
        return rule.enabled
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
