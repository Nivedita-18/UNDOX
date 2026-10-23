"""
Workflow service containing business logic for creating and retrieving workflows.
Handles database transactions and eager loading to prevent N+1 queries.
"""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.workflow import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from backend.app.schemas.workflow import WorkflowCreate


def create_workflow(db: Session, data: WorkflowCreate) -> WorkflowInstance:
    """
    Creates a new WorkflowInstance along with all its planned steps in a single transaction.
    Rolls back automatically if an error occurs.
    """
    workflow = WorkflowInstance(
        name=data.name,
        status=WorkflowStatus.PENDING.value,
    )

    for step_data in data.steps:
        step = WorkflowStep(
            name=step_data.name,
            step_order=step_data.step_order,
            status=StepStatus.PENDING.value,
        )
        workflow.steps.append(step)

    try:
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        # Ensure steps are populated on the refreshed instance
        for step in workflow.steps:
            db.refresh(step)
        return workflow
    except Exception:
        db.rollback()
        raise


def get_workflow_by_id(db: Session, workflow_id: UUID) -> Optional[WorkflowInstance]:
    """
    Retrieves a single workflow by its UUID with steps eagerly loaded and ordered by step_order.
    Avoids N+1 query overhead.
    """
    stmt = (
        select(WorkflowInstance)
        .options(selectinload(WorkflowInstance.steps))
        .where(WorkflowInstance.id == workflow_id)
    )
    result = db.execute(stmt).scalar_one_or_none()
    return result


def list_workflows(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[WorkflowInstance], int]:
    """
    Lists recent workflows sorted by creation timestamp (newest first)
    along with the total count of workflows.
    Uses selectinload to eagerly fetch steps without N+1 query penalties.
    """
    # Total count query
    total_stmt = select(func.count()).select_from(WorkflowInstance)
    total = db.execute(total_stmt).scalar() or 0

    # Paginated items query
    items_stmt = (
        select(WorkflowInstance)
        .options(selectinload(WorkflowInstance.steps))
        .order_by(WorkflowInstance.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.execute(items_stmt).scalars().all())

    return items, total
