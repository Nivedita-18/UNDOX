"""
REST API router for failure recovery planning.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user, require_role
from backend.app.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.recovery.conflicts import detect_recovery_conflicts
from backend.app.recovery.executor import (
    approve_recovery_plan,
    execute_recovery_plan,
    get_recovery_execution_status,
    reject_recovery_plan,
)
from backend.app.recovery.service import (
    ExecutionNotFailedError,
    ExecutionNotFoundError,
    RecoveryPlanExecutionConflictError,
    RecoveryPlanNotApprovedError,
    RecoveryPlanNotFoundError,
    RecoveryPlanStaleError,
    RecoveryPlanUnauthorizedActionError,
    get_recovery_plan_by_id,
    list_recovery_plans_for_execution,
    plan_recovery_for_execution,
)
from backend.app.schemas.recovery import (
    RecoveryExecutionRequest,
    RecoveryExecutionStatusResponse,
    RecoveryPlanApprovalRequest,
    RecoveryPlanConflictReport,
    RecoveryPlanRejectionRequest,
    RecoveryPlanRequest,
    RecoveryPlanResponse,
)

router = APIRouter(
    tags=["Recovery"],
)


@router.post(
    "/executions/{execution_id}/recovery-plans",
    response_model=RecoveryPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a failure recovery plan for a failed execution",
)
def create_recovery_plan(
    execution_id: UUID,
    payload: Optional[RecoveryPlanRequest] = None,
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Generates a structured, auditable failure recovery plan for an existing failed execution.

    - Analyzes completed steps, failed steps, and pending steps.
    - Determines compensation strategy (reverse-order Saga rollback).
    - Detects unsupported or irreversible actions and flags them for manual review.
    - Preserves the original execution history without mutation.
    - Returns HTTP 201 with the generated plan and ordered recovery actions.
    - Returns HTTP 404 if the execution does not exist.
    - Returns HTTP 400 if the execution is not in FAILED status.
    """
    try:
        plan = plan_recovery_for_execution(db, execution_id, payload)
        return plan
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ExecutionNotFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/recovery-plans/{plan_id}",
    response_model=RecoveryPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a recovery plan by ID",
)
def get_recovery_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the details and ordered proposed actions of a specific recovery plan.

    - Returns HTTP 200 with plan details and actions.
    - Returns HTTP 404 if no plan exists with the given ID.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery plan with ID '{plan_id}' not found.",
        )
    return plan


@router.get(
    "/executions/{execution_id}/recovery-plans",
    response_model=List[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="List recovery plans for an execution",
)
def list_recovery_plans(
    execution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves all recovery plans generated for a specific workflow execution,
    sorted with the newest plan first.
    """
    try:
        plans = list_recovery_plans_for_execution(db, execution_id)
        return plans
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/recovery-plans/{plan_id}/conflicts",
    response_model=RecoveryPlanConflictReport,
    status_code=status.HTTP_200_OK,
    summary="Inspect conflicts and staleness for a recovery plan",
)
def inspect_recovery_plan_conflicts(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates an existing recovery plan for conflicts, staleness, and manual review requirements.

    - Detects whether the plan is stale due to state changes in execution or workflow.
    - Identifies conflicting actions targeting the same step or violating execution order.
    - Flags irreversible actions or actions requiring manual review.
    - Computes conflict count and highest severity level (CRITICAL, HIGH, MEDIUM, LOW).
    - Returns HTTP 200 with the full conflict report.
    - Returns HTTP 404 if the recovery plan does not exist.
    """
    try:
        report = detect_recovery_conflicts(db, plan_id)
        return report
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/recovery-plans/{plan_id}/approve",
    response_model=RecoveryPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a recovery plan for execution",
)
def approve_plan(
    plan_id: UUID,
    payload: Optional[RecoveryPlanApprovalRequest] = None,
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Approves a recovery plan, enabling execution.
    Requires 'authorize_manual_review=True' if plan has irreversible actions or manual review requirements.
    Requires OPERATOR or ADMIN role.
    """
    req = payload or RecoveryPlanApprovalRequest()
    if not payload or not payload.operator or payload.operator == "operator":
        req.operator = current_user.username

    try:
        plan = approve_recovery_plan(db, plan_id, req)
        return plan
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (RecoveryPlanStaleError, RecoveryPlanUnauthorizedActionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RecoveryPlanExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/recovery-plans/{plan_id}/reject",
    response_model=RecoveryPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a recovery plan",
)
def reject_plan(
    plan_id: UUID,
    payload: Optional[RecoveryPlanRejectionRequest] = None,
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Rejects a recovery plan, preventing its execution.
    Stores the operator identity and rejection reason.
    Requires OPERATOR or ADMIN role.
    """
    req = payload or RecoveryPlanRejectionRequest(reason="Rejected by operator")
    if not payload or not payload.operator or payload.operator == "operator":
        req.operator = current_user.username

    try:
        plan = reject_recovery_plan(db, plan_id, req)
        return plan
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RecoveryPlanExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/recovery-plans/{plan_id}/execute",
    response_model=RecoveryPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute an approved recovery plan",
)
def execute_plan(
    plan_id: UUID,
    payload: Optional[RecoveryExecutionRequest] = None,
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Controlled execution of an approved recovery plan using simulated actions.
    Enforces sequential action ordering, conflict checks, and duplicate prevention.
    Requires OPERATOR or ADMIN role.
    """
    try:
        plan = execute_recovery_plan(db, plan_id, payload)
        return plan
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (RecoveryPlanNotApprovedError, RecoveryPlanStaleError, RecoveryPlanUnauthorizedActionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RecoveryPlanExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/recovery-plans/{plan_id}/execution-status",
    response_model=RecoveryExecutionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve runtime execution status and progress for a recovery plan",
)
def get_execution_status(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves runtime execution status and progress metrics for a recovery plan.
    """
    try:
        status_report = get_recovery_execution_status(db, plan_id)
        return status_report
    except RecoveryPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

