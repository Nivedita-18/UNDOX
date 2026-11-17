
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import WorkflowInstance, WorkflowStep
from ..schemas.workflow import WorkflowCreate
from ..audit.service import record_audit_event


# Create a new workflow
def create_workflow(
    db: Session,
    workflow_data: WorkflowCreate,
    created_by: int | None = None
):

    try:
        workflow = WorkflowInstance(
            name=workflow_data.name,
            description=workflow_data.description,
            status="ACTIVE",
            created_by=created_by
        )

        db.add(workflow)
        db.flush()

        ordered_steps = sorted(
            workflow_data.steps,
            key=lambda step: step.step_order
        )

        for step_data in ordered_steps:

            step = WorkflowStep(
                workflow_id=workflow.id,
                name=step_data.name,
                step_order=step_data.step_order,
                payload=step_data.payload,
                compensation_payload=(
                    step_data.compensation_payload
                ),
                is_reversible=step_data.is_reversible
            )

            db.add(step)

        workflow_id = workflow.id

        # Record audit event
        record_audit_event(
            db,
            event_type="WORKFLOW_CREATED",
            outcome="SUCCESS",
            message="Workflow created successfully",
            actor_id=created_by,
            event_data={
                "workflow_id": workflow_id,
                "workflow_name": workflow.name
            }
        )

        db.commit()

        return get_workflow(db, workflow_id)

    except Exception:
        db.rollback()
        raise


# Get all workflows with pagination
def list_workflows(
    db: Session,
    limit: int = 20,
    offset: int = 0
):

    statement = (
        select(WorkflowInstance)
        .options(
            selectinload(WorkflowInstance.steps)
        )
        .order_by(WorkflowInstance.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


# Get one workflow by ID
def get_workflow(
    db: Session,
    workflow_id: int
):

    statement = (
        select(WorkflowInstance)
        .options(
            selectinload(WorkflowInstance.steps)
        )
        .where(
            WorkflowInstance.id == workflow_id
        )
    )

    return db.scalar(statement)
