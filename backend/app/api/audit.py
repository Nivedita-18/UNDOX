"""
API router for UNDOX Audit History and Activity Logging.

Provides endpoints to:
- Retrieve paginated audit event logs.
- Filter audit logs by execution_id, recovery_plan_id, event_type, and outcome.
- Retrieve individual audit event logs by ID.
- Provide sub-resource audit event endpoints for executions and recovery plans.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.audit.service import (
    AuditEventNotFoundError,
    ExecutionNotFoundError,
    RecoveryPlanNotFoundError,
    get_audit_event_by_id,
    query_audit_events,
)
from backend.app.auth.dependencies import get_current_user
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.audit import AuditEventResponse, AuditEventsListResponse

router = APIRouter(prefix="/api/v1", tags=["Audit History"])


@router.get(
    "/audit-events",
    response_model=AuditEventsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List and filter audit events",
    description="Retrieve paginated audit activity records filtered by execution, plan, event type, or outcome.",
)
def list_audit_events(
    execution_id: Optional[UUID] = Query(None, description="Filter by workflow execution ID"),
    recovery_plan_id: Optional[UUID] = Query(None, description="Filter by recovery plan ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventsListResponse:
    try:
        items, total = query_audit_events(
            db=db,
            execution_id=execution_id,
            recovery_plan_id=recovery_plan_id,
            event_type=event_type,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
        return AuditEventsListResponse(
            items=[AuditEventResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/audit-events/{event_id}",
    response_model=AuditEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audit event by ID",
    description="Retrieve a single audit event record by its unique ID.",
)
def get_audit_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventResponse:
    event = get_audit_event_by_id(db, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event with ID '{event_id}' not found.",
        )
    return AuditEventResponse.model_validate(event)


@router.get(
    "/executions/{execution_id}/audit-events",
    response_model=AuditEventsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List audit events for an execution",
    description="Retrieve paginated audit events specifically linked to a workflow execution attempt.",
)
def list_execution_audit_events(
    execution_id: UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventsListResponse:
    try:
        items, total = query_audit_events(
            db=db,
            execution_id=execution_id,
            event_type=event_type,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
        return AuditEventsListResponse(
            items=[AuditEventResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/recovery-plans/{plan_id}/audit-events",
    response_model=AuditEventsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List audit events for a recovery plan",
    description="Retrieve paginated audit events specifically linked to a recovery plan.",
)
def list_recovery_plan_audit_events(
    plan_id: UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventsListResponse:
    try:
        items, total = query_audit_events(
            db=db,
            recovery_plan_id=plan_id,
            event_type=event_type,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
        return AuditEventsListResponse(
            items=[AuditEventResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
