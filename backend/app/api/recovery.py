
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from ..database import get_db

from ..schemas.recovery import (
    RecoveryPlanRead,
    RecoveryDecision,
    RecoveryExecutionStatusRead
)

from ..recovery import service
from ..recovery import executor

from ..auth.dependencies import (
    get_current_user,
    require_roles
)


router = APIRouter(tags=["Recovery"])


# Generate recovery plan - ADMIN and OPERATOR
@router.post(
    "/executions/{execution_id}/recovery-plans",
    response_model=RecoveryPlanRead,
    status_code=status.HTTP_201_CREATED
)
def generate_recovery(
    execution_id: int,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    try:
        return service.generate_recovery_plan(
            db,
            execution_id,
            created_by=current_user.id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except service.InvalidRecoveryStateError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# List plans for an execution - authenticated users
@router.get(
    "/executions/{execution_id}/recovery-plans",
    response_model=list[RecoveryPlanRead]
)
def list_recovery(
    execution_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try:
        return service.list_recovery_plans(
            db,
            execution_id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )


# Retrieve a recovery plan - authenticated users
@router.get(
    "/recovery-plans/{plan_id}",
    response_model=RecoveryPlanRead
)
def get_recovery(
    plan_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try:
        return service.get_recovery_plan(
            db,
            plan_id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )


# Inspect conflicts - authenticated users
@router.get(
    "/recovery-plans/{plan_id}/conflicts"
)
def check_conflicts(
    plan_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try:
        return service.check_plan_conflicts(
            db,
            plan_id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )


# Approve recovery plan - ADMIN and OPERATOR
@router.post(
    "/recovery-plans/{plan_id}/approve",
    response_model=RecoveryPlanRead
)
def approve_recovery(
    plan_id: int,
    request: RecoveryDecision,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    try:
        return service.approve_recovery_plan(
            db,
            plan_id,
            request.reason,
            request.manual_review_acknowledged,
            reviewer_id=current_user.id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except service.RecoveryConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )

    except service.ManualReviewRequiredError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except service.InvalidRecoveryStateError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# Reject recovery plan - ADMIN and OPERATOR
@router.post(
    "/recovery-plans/{plan_id}/reject",
    response_model=RecoveryPlanRead
)
def reject_recovery(
    plan_id: int,
    request: RecoveryDecision,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    try:
        return service.reject_recovery_plan(
            db,
            plan_id,
            request.reason,
            reviewer_id=current_user.id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except service.InvalidRecoveryStateError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# Execute recovery - ADMIN and OPERATOR
@router.post(
    "/recovery-plans/{plan_id}/execute",
    response_model=RecoveryPlanRead
)
def execute_recovery(
    plan_id: int,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    try:
        return executor.execute_recovery_plan(
            db,
            plan_id,
            executed_by=current_user.id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except executor.RecoveryExecutionError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# Check recovery execution progress - authenticated users
@router.get(
    "/recovery-plans/{plan_id}/execution-status",
    response_model=RecoveryExecutionStatusRead
)
def recovery_execution_status(
    plan_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try:
        return service.get_recovery_execution_status(
            db,
            plan_id
        )

    except service.RecoveryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )
