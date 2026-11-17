
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)

from sqlalchemy.orm import Session

from ..database import get_db

from ..schemas.execution import (
    ExecutionRequest,
    ExecutionRead
)

from ..executions import service

from ..auth.dependencies import (
    get_current_user,
    require_roles
)


router = APIRouter(
    tags=["Executions"]
)


# Execute workflow - ADMIN and OPERATOR only
@router.post(
    "/workflows/{workflow_id}/execute",
    response_model=ExecutionRead,
    status_code=status.HTTP_201_CREATED
)
def execute_workflow(
    workflow_id: int,
    request: ExecutionRequest,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    try:

        return service.execute_workflow(
            db=db,
            workflow_id=workflow_id,
            simulate_failure=request.simulate_failure,
            failure_step_order=request.failure_step_order,
            failure_message=request.failure_message,
            triggered_by=current_user.id
        )

    except service.WorkflowNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Workflow not found"
        )

    except service.InactiveWorkflowError:

        raise HTTPException(
            status_code=409,
            detail="Workflow is not active"
        )

    except service.ExecutionConflictError:

        raise HTTPException(
            status_code=409,
            detail="An execution is already running"
        )

    except service.InvalidFailureStepError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error)
        )


# Get individual execution - authenticated users
@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionRead
)
def get_execution(
    execution_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    execution = service.get_execution(
        db,
        execution_id
    )

    if execution is None:

        raise HTTPException(
            status_code=404,
            detail="Execution not found"
        )

    return execution


# List workflow executions - authenticated users
@router.get(
    "/workflows/{workflow_id}/executions",
    response_model=list[ExecutionRead]
)
def list_executions(
    workflow_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    executions = service.list_workflow_executions(
        db,
        workflow_id,
        limit,
        offset
    )

    if executions is None:

        raise HTTPException(
            status_code=404,
            detail="Workflow not found"
        )

    return executions
