"""Database package for the gateway.

This package provides:
- Database models (Student, Conversation, Rule, QuotaLog)
- Synchronous and asynchronous session management
- CRUD operations for all models
- FastAPI dependency injection support
"""

from gateway.app.db.base import Base
from gateway.app.db.models import Conversation, QuotaLog, Rule, Student
from gateway.app.db.session import get_engine, get_session, get_session_maker
from gateway.app.db.async_session import (
    close_async_engine,
    get_async_engine,
    get_async_session,
    get_async_session_maker,
    get_db,
    init_async_db,
    SessionDep,
)
from gateway.app.db.dependencies import SessionDep as SessionDepAlias
from gateway.app.db.crud import (
    check_and_consume_quota,
    create_quota_log,
    create_rule,
    delete_rule,
    get_all_rules,
    get_conversations_by_student,
    get_quota_logs_by_student,
    get_recent_conversations,
    get_rule_by_id,
    get_student_by_id,
    list_students,
    lookup_student_by_hash,
    save_conversation,
    save_conversation_bulk,
    toggle_rule_enabled,
    update_rule,
    update_student_quota,
    update_student_quota_bulk,
)

__all__ = [
    # Base
    "Base",
    # Models
    "Conversation",
    "QuotaLog",
    "Rule",
    "Student",
    # Session (sync)
    "get_engine",
    "get_session",
    "get_session_maker",
    # Session (async)
    "close_async_engine",
    "get_async_engine",
    "get_async_session",
    "get_async_session_maker",
    "get_db",
    "init_async_db",
    # FastAPI Dependencies
    "SessionDep",
    "SessionDepAlias",
    # CRUD - Student
    "check_and_consume_quota",
    "get_student_by_id",
    "list_students",
    "lookup_student_by_hash",
    "update_student_quota",
    "update_student_quota_bulk",
    # CRUD - Conversation
    "get_conversations_by_student",
    "get_recent_conversations",
    "save_conversation",
    "save_conversation_bulk",
    # CRUD - Rule
    "create_rule",
    "delete_rule",
    "get_all_rules",
    "get_rule_by_id",
    "toggle_rule_enabled",
    "update_rule",
    # CRUD - QuotaLog
    "create_quota_log",
    "get_quota_logs_by_student",
]
