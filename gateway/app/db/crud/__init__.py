"""CRUD operations package."""

# Student operations (moved to student.py)
from gateway.app.db.crud.student import (
    lookup_student_by_hash,
    get_student_by_id,
    list_students,
    update_student_quota,
    update_student_quota_bulk,
)

# Conversation operations (moved to conversation.py)
from gateway.app.db.crud.conversation import (
    save_conversation,
    save_conversation_bulk,
    get_conversations_by_student,
    get_recent_conversations,
)

# Quota operations (moved to quota.py)
from gateway.app.db.crud.quota import (
    check_and_consume_quota,
    create_quota_log,
    get_quota_logs_by_student,
)

# Re-export from legacy crud until fully migrated
from gateway.app.db._crud_legacy import (
    create_rule,
    delete_rule,
    get_all_rules,
    get_rule_by_id,
    toggle_rule_enabled,
    update_rule,
)

__all__ = [
    # Student operations
    "lookup_student_by_hash",
    "get_student_by_id",
    "list_students",
    "update_student_quota",
    "update_student_quota_bulk",
    # Conversation operations
    "save_conversation",
    "save_conversation_bulk",
    "get_conversations_by_student",
    "get_recent_conversations",
    # Quota operations
    "check_and_consume_quota",
    "create_quota_log",
    "get_quota_logs_by_student",
    # Re-exported from legacy (rule operations)
    "create_rule",
    "delete_rule",
    "get_all_rules",
    "get_rule_by_id",
    "toggle_rule_enabled",
    "update_rule",
]
