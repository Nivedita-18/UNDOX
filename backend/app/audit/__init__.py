"""
Audit package for UNDOX.
"""

from backend.app.audit.sanitizer import sanitize_details, sanitize_text
from backend.app.audit.service import (
    AuditEventNotFoundError,
    AuditError,
    ExecutionNotFoundError,
    RecoveryPlanNotFoundError,
    get_audit_event_by_id,
    query_audit_events,
    record_audit_event,
)

__all__ = [
    "sanitize_text",
    "sanitize_details",
    "AuditError",
    "AuditEventNotFoundError",
    "ExecutionNotFoundError",
    "RecoveryPlanNotFoundError",
    "record_audit_event",
    "get_audit_event_by_id",
    "query_audit_events",
]
