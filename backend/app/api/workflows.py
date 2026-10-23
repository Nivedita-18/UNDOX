"""
REST API router for workflow registration and inspection.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
)
from backend.app.workflows.service import (
    create_workflow,
    get_workflow_by_id,
    list_workflows,
)

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new workflow with planned steps",
)
def register_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
):
    """
    Registers a new workflow along with its planned execution steps.
    All steps must follow strict sequential ordering starting at 1.
    Initial status for both the workflow and its steps is PENDING.
    """
    created = create_workflow(db, payload)
    return created


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve workflow details and ordered steps",
)
def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieves the full details of a workflow instance, including all steps
    ordered by their execution sequence (step_order).
    Returns 404 if no workflow exists with the given UUID.
    """
    workflow = get_workflow_by_id(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return workflow


@router.get(
    "",
    response_model=WorkflowListResponse,
    status_code=status.HTTP_200_OK,
    summary="List recent workflows",
)
def get_workflows(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of workflows to return (between 1 and 100)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of workflows to skip for pagination",
    ),
    db: Session = Depends(get_db),
):
    """
    Lists recent workflows sorted by creation timestamp (newest first).
    Enforces bounded limit parameter to protect database performance.
    """
    items, total = list_workflows(db, limit=limit, offset=offset)
    return WorkflowListResponse(items=items, total=total)
