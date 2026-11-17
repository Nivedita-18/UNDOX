
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    WorkflowInstance,
    WorkflowExecution,
    ExecutionStep
)

from ..audit.service import record_audit_event


class WorkflowNotFoundError(Exception):
    pass


class InactiveWorkflowError(Exception):
    pass


class ExecutionConflictError(Exception):
    pass


class InvalidFailureStepError(Exception):
    pass


def get_execution(
    db: Session,
    execution_id: int
):

    statement = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.steps)
        )
        .where(
            WorkflowExecution.id == execution_id
        )
    )

    return db.scalar(statement)


def execute_workflow(
    db: Session,
    workflow_id: int,
    simulate_failure: bool = False,
    failure_step_order: int | None = None,
    failure_message: str = "Simulated workflow step failure",
    triggered_by: int | None = None
):

    try:

        # Lock workflow to avoid conflicting executions
        statement = (
            select(WorkflowInstance)
            .options(
                selectinload(WorkflowInstance.steps)
            )
            .where(
                WorkflowInstance.id == workflow_id
            )
            .with_for_update()
        )

        workflow = db.scalar(statement)

        if workflow is None:
            raise WorkflowNotFoundError()

        if workflow.status != "ACTIVE":
            raise InactiveWorkflowError()

        # Check active execution
        active_execution = db.scalar(
            select(WorkflowExecution.id)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.status == "RUNNING"
            )
            .limit(1)
        )

        if active_execution is not None:
            raise ExecutionConflictError()

        ordered_steps = sorted(
            workflow.steps,
            key=lambda step: step.step_order
        )

        if not ordered_steps:
            raise ValueError(
                "Workflow does not contain any steps"
            )

        valid_orders = {
            step.step_order for step in ordered_steps
        }

        if simulate_failure:
            if failure_step_order not in valid_orders:
                raise InvalidFailureStepError(
                    "Failure step does not exist in this workflow"
                )

        now = datetime.now(timezone.utc)

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            triggered_by=triggered_by,
            status="RUNNING",
            started_at=now
        )

        db.add(execution)
        db.flush()

        failure_triggered = False

        # Execute sequential steps
        for step in ordered_steps:

            step_started_at = None
            step_finished_at = now
            output_payload = None
            error_message = None

            if failure_triggered:

                step_status = "SKIPPED"

            elif (
                simulate_failure
                and step.step_order == failure_step_order
            ):

                step_status = "FAILED"
                step_started_at = now
                error_message = failure_message
                failure_triggered = True

            else:

                step_status = "COMPLETED"
                step_started_at = now

                output_payload = {
                    "simulated": True,
                    "step_name": step.name,
                    "message": "Step completed successfully"
                }

            execution_step = ExecutionStep(
                execution_id=execution.id,
                workflow_step_id=step.id,
                step_name=step.name,
                step_order=step.step_order,
                status=step_status,
                input_payload=dict(step.payload or {}),
                output_payload=output_payload,
                error_message=error_message,
                started_at=step_started_at,
                finished_at=step_finished_at
            )

            db.add(execution_step)

        # Final execution status
        if failure_triggered:

            execution.status = "FAILED"
            execution.error_message = failure_message

        else:

            execution.status = "COMPLETED"
            execution.error_message = None

        execution.finished_at = datetime.now(timezone.utc)

        execution_id = execution.id

        # Record audit event
        record_audit_event(
            db,
            event_type=(
                "WORKFLOW_EXECUTION_FAILED"
                if failure_triggered
                else "WORKFLOW_EXECUTION_COMPLETED"
            ),
            outcome=execution.status,
            message=(
                execution.error_message
                or "Execution completed successfully"
            ),
            actor_id=triggered_by,
            execution_id=execution_id,
            event_data={
                "workflow_id": workflow_id,
                "execution_id": execution_id
            }
        )

        db.commit()

        return get_execution(db, execution_id)

    except Exception:
        db.rollback()
        raise


# List executions for a workflow
def list_workflow_executions(
    db: Session,
    workflow_id: int,
    limit: int = 20,
    offset: int = 0
):

    workflow = db.get(
        WorkflowInstance,
        workflow_id
    )

    if workflow is None:
        return None

    statement = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.steps)
        )
        .where(
            WorkflowExecution.workflow_id == workflow_id
        )
        .order_by(WorkflowExecution.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())
