"""CRUD operations package.

Refactored package structure splitting the original 593-line crud.py into:
- student.py: Student-related operations
- conversation.py: Conversation-related operations
- quota.py: Quota-related operations
- rule.py: Rule-related operations
"""

# Student operations
from gateway.app.db.crud.student import (
    lookup_student_by_hash,
    get_student_by_id,
    list_students,
    update_student_quota,
    update_student_quota_bulk,
    get_quota_logs_by_student,
)

# Conversation operations
from gateway.app.db.crud.conversation import (
    save_conversation,
    save_conversation_bulk,
    get_conversations_by_student,
    get_recent_conversations,
)

# Quota operations
from gateway.app.db.crud.quota import (
    check_and_consume_quota,
    create_quota_log,
)

# Rule operations
from gateway.app.db.crud.rule import (
    get_all_rules,
    get_rule_by_id,
    create_rule,
    update_rule,
    delete_rule,
    toggle_rule_enabled,
)

__all__ = [
    # Student operations
    "lookup_student_by_hash",
    "get_student_by_id",
    "list_students",
    "update_student_quota",
    "update_student_quota_bulk",
    "get_quota_logs_by_student",
    # Conversation operations
    "save_conversation",
    "save_conversation_bulk",
    "get_conversations_by_student",
    "get_recent_conversations",
    # Quota operations
    "check_and_consume_quota",
    "create_quota_log",
    # Rule operations
    "get_all_rules",
    "get_rule_by_id",
    "create_rule",
    "update_rule",
    "delete_rule",
    "toggle_rule_enabled",
]
