
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent


# Create an audit event inside the current database transaction
def record_audit_event(
    db: Session,
    event_type: str,
    outcome: str = "SUCCESS",
    message: str | None = None,
    actor_id: int | None = None,
    execution_id: int | None = None,
    recovery_plan_id: int | None = None,
    event_data: dict[str, Any] | None = None
) -> AuditEvent:

    event = AuditEvent(
        event_type=event_type,
        outcome=outcome,
        message=message,
        actor_id=actor_id,
        execution_id=execution_id,
        recovery_plan_id=recovery_plan_id,
        event_data=event_data
    )

    db.add(event)

    return event


# Retrieve audit events with optional filters and pagination
def list_audit_events(
    db: Session,
    event_type: str | None = None,
    outcome: str | None = None,
    execution_id: int | None = None,
    recovery_plan_id: int | None = None,
    limit: int = 50,
    offset: int = 0
) -> list[AuditEvent]:

    statement = select(AuditEvent)

    # Filter by event type
    if event_type is not None:
        statement = statement.where(
            AuditEvent.event_type == event_type
        )

    # Filter by outcome
    if outcome is not None:
        statement = statement.where(
            AuditEvent.outcome == outcome
        )

    # Filter by execution ID
    if execution_id is not None:
        statement = statement.where(
            AuditEvent.execution_id == execution_id
        )

    # Filter by recovery plan ID
    if recovery_plan_id is not None:
        statement = statement.where(
            AuditEvent.recovery_plan_id == recovery_plan_id
        )

    # Newest events first, with stable ordering
    statement = (
        statement
        .order_by(
            AuditEvent.created_at.desc(),
            AuditEvent.id.desc()
        )
        .limit(limit)
        .offset(offset)
    )

    return list(
        db.scalars(statement).all()
    )
