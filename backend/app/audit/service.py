"""
Audit Service for UNDOX.

Manages persistent, append-only activity logging for:
- Workflow executions (start, completion, failure)
- Recovery planning (plan creation)
- Recovery decisions (operator approval, rejection)
- Recovery execution (start, completion, failure)

Guarantees:
- Historical records are preserved even when operations fail.
- Sensitive data (passwords, tokens, credentials) is automatically sanitized.
- Safe query and pagination functionality with existence checks for target resources.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.audit.sanitizer import sanitize_details, sanitize_text
from backend.app.models.audit import AuditEvent, AuditEventType, AuditOutcome
from backend.app.models.execution import WorkflowExecution
from backend.app.models.recovery import RecoveryPlan


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AuditError(Exception):
    """Base exception for audit service operations."""
    pass


class AuditEventNotFoundError(AuditError):
    """Raised when an audit event by ID is not found."""
    pass


class ExecutionNotFoundError(AuditError):
    """Raised when an execution filtered by ID does not exist."""
    pass


class RecoveryPlanNotFoundError(AuditError):
    """Raised when a recovery plan filtered by ID does not exist."""
    pass


# ---------------------------------------------------------------------------
# Recording API
# ---------------------------------------------------------------------------

def record_audit_event(
    db: Session,
    event_type: Union[AuditEventType, str],
    outcome: Union[AuditOutcome, str],
    message: str,
    execution_id: Optional[UUID] = None,
    recovery_plan_id: Optional[UUID] = None,
    actor: Optional[str] = "system",
    details: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> AuditEvent:
    """
    Appends an immutable audit event to the audit_events table.
    Automatically redacts sensitive secrets and passwords from message and details.
    """
    type_str = event_type.value if isinstance(event_type, AuditEventType) else str(event_type)
    outcome_str = outcome.value if isinstance(outcome, AuditOutcome) else str(outcome)

    safe_message = sanitize_text(message)
    safe_details = sanitize_details(details) if details is not None else None

    event = AuditEvent(
        event_type=type_str,
        outcome=outcome_str,
        message=safe_message,
        execution_id=execution_id,
        recovery_plan_id=recovery_plan_id,
        actor=actor or "system",
        details=safe_details,
        timestamp=datetime.now(timezone.utc),
    )

    db.add(event)
    if commit:
        try:
            db.commit()
            db.refresh(event)
        except Exception:
            db.rollback()
            raise

    return event


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------

def get_audit_event_by_id(db: Session, event_id: UUID) -> Optional[AuditEvent]:
    """Retrieves a single audit event record by its primary key."""
    stmt = select(AuditEvent).where(AuditEvent.id == event_id)
    return db.execute(stmt).scalar_one_or_none()


def query_audit_events(
    db: Session,
    execution_id: Optional[UUID] = None,
    recovery_plan_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AuditEvent], int]:
    """
    Retrieves filtered and paginated audit events ordered chronologically descending.

    Validations:
    - If execution_id is provided, verifies that the execution exists (raises ExecutionNotFoundError if missing).
    - If recovery_plan_id is provided, verifies that the recovery plan exists (raises RecoveryPlanNotFoundError if missing).
    """
    # 1. Resource existence checks
    if execution_id is not None:
        exec_check = db.execute(
            select(WorkflowExecution.id).where(WorkflowExecution.id == execution_id)
        ).scalar_one_or_none()
        if exec_check is None:
            raise ExecutionNotFoundError(f"Execution with ID '{execution_id}' not found.")

    if recovery_plan_id is not None:
        plan_check = db.execute(
            select(RecoveryPlan.id).where(RecoveryPlan.id == recovery_plan_id)
        ).scalar_one_or_none()
        if plan_check is None:
            raise RecoveryPlanNotFoundError(f"Recovery plan with ID '{recovery_plan_id}' not found.")

    # 2. Build filter conditions
    base_stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))

    if execution_id is not None:
        base_stmt = base_stmt.where(AuditEvent.execution_id == execution_id)
        count_stmt = count_stmt.where(AuditEvent.execution_id == execution_id)

    if recovery_plan_id is not None:
        base_stmt = base_stmt.where(AuditEvent.recovery_plan_id == recovery_plan_id)
        count_stmt = count_stmt.where(AuditEvent.recovery_plan_id == recovery_plan_id)

    if event_type is not None:
        base_stmt = base_stmt.where(AuditEvent.event_type == event_type)
        count_stmt = count_stmt.where(AuditEvent.event_type == event_type)

    if outcome is not None:
        base_stmt = base_stmt.where(AuditEvent.outcome == outcome)
        count_stmt = count_stmt.where(AuditEvent.outcome == outcome)

    # 3. Total count
    total_count = db.execute(count_stmt).scalar() or 0

    # 4. Ordering and pagination (chronological descending: newest first)
    query_stmt = (
        base_stmt
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.execute(query_stmt).scalars().all())

    return items, total_count
