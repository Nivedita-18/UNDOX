
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db

from ..models import (
    AuditEvent,
    WorkflowExecution,
    RecoveryPlan
)

from ..schemas.audit import AuditEventRead

from ..audit import service

from ..auth.dependencies import require_roles


router = APIRouter(
    prefix="/api/v1",
    tags=["Audit"]
)


# ADMIN and OPERATOR can access audit history
AUDIT_ACCESS = require_roles(
    "ADMIN",
    "OPERATOR"
)


# List and filter audit events
@router.get(
    "/audit-events",
    response_model=list[AuditEventRead]
)
def list_events(
    event_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=100
    ),
    outcome: str | None = Query(
        default=None,
        min_length=1,
        max_length=50
    ),
    execution_id: int | None = Query(
        default=None,
        gt=0
    ),
    recovery_plan_id: int | None = Query(
        default=None,
        gt=0
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(AUDIT_ACCESS),
    db: Session = Depends(get_db)
):

    return service.list_audit_events(
        db,
        event_type,
        outcome,
        execution_id,
        recovery_plan_id,
        limit,
        offset
    )


# Retrieve a single audit event
@router.get(
    "/audit-events/{event_id}",
    response_model=AuditEventRead
)
def get_event(
    event_id: int,
    current_user=Depends(AUDIT_ACCESS),
    db: Session = Depends(get_db)
):

    event = db.get(
        AuditEvent,
        event_id
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Audit event not found"
        )

    return event


# Events associated with an execution
@router.get(
    "/executions/{execution_id}/audit-events",
    response_model=list[AuditEventRead]
)
def execution_events(
    execution_id: int,
    current_user=Depends(AUDIT_ACCESS),
    db: Session = Depends(get_db)
):

    execution = db.get(
        WorkflowExecution,
        execution_id
    )

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="Execution not found"
        )

    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.execution_id == execution_id
        )
        .order_by(
            AuditEvent.created_at.desc()
        )
    )

    return list(
        db.scalars(statement).all()
    )


# Events associated with a recovery plan
@router.get(
    "/recovery-plans/{plan_id}/audit-events",
    response_model=list[AuditEventRead]
)
def recovery_events(
    plan_id: int,
    current_user=Depends(AUDIT_ACCESS),
    db: Session = Depends(get_db)
):

    plan = db.get(
        RecoveryPlan,
        plan_id
    )

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Recovery plan not found"
        )

    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.recovery_plan_id == plan_id
        )
        .order_by(
            AuditEvent.created_at.desc()
        )
    )

    return list(
        db.scalars(statement).all()
    )
