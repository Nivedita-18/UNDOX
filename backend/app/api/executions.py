"""
REST API router for workflow execution and inspection.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.executions.service import (
    ActiveExecutionConflictError,
    InvalidFailureConfigError,
    WorkflowNotFoundError,
    execute_workflow,
    get_execution_by_id,
)
from backend.app.schemas.execution import (
    ExecutionRequest,
    ExecutionResponse,
)

router = APIRouter(
    tags=["Executions"],
)


@router.post(
    "/workflows/{workflow_id}/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger execution of a workflow instance",
)
def trigger_workflow_execution(
    workflow_id: UUID,
    payload: Optional[ExecutionRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Triggers execution of an existing workflow instance.
    Optionally accepts a failure simulation configuration to test error handling
    and failure recovery without real external outages.

    - Returns 201 with full execution state and step records.
    - Returns 404 if the workflow does not exist.
    - Returns 400 if the failure simulation targets a nonexistent step.
    - Returns 409 if an execution is already PENDING or RUNNING for this workflow.
    """
    request_data = payload if payload is not None else ExecutionRequest()
    try:
        execution = execute_workflow(db, workflow_id, request_data)
        return execution
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InvalidFailureConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except ActiveExecutionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve execution details by ID",
)
def get_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieves the execution details and runtime step statuses for a specific
    WorkflowExecution attempt.

    - Returns 200 with full execution details and step states.
    - Returns 404 if no execution exists with the given ID.
    """
    execution = get_execution_by_id(db, execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID '{execution_id}' not found.",
        )
    return execution
