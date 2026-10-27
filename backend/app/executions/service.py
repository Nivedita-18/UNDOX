"""
Workflow execution service for UNDOX.

Implements the domain-neutral simulation engine that:
- Initialises a WorkflowExecution with row-level locking to prevent duplicates.
- Executes steps sequentially using short-lived database transactions.
- Supports controlled failure injection via FailureSimulationConfig.
- Stores all runtime results in WorkflowExecution / ExecutionStep only;
  never overwrites WorkflowStep fields or historical execution records.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    WorkflowExecution,
)
from backend.app.models.workflow import (
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
)
from backend.app.schemas.execution import ExecutionRequest


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ExecutionError(Exception):
    """Base exception for execution service errors."""
    pass


class WorkflowNotFoundError(ExecutionError):
    """Raised when the requested workflow does not exist."""
    pass


class InvalidFailureConfigError(ExecutionError):
    """Raised when failure_simulation references a step_order that does not exist."""
    pass


class ActiveExecutionConflictError(ExecutionError):
    """Raised when an execution is already PENDING or RUNNING for the workflow."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _simulate_step_work(step_name: str) -> Dict[str, Any]:
    """
    Simulates processing work for a step.
    Returns a domain-neutral output dict.
    In a real system this would call external services.
    """
    return {
        "simulated": True,
        "step_name": step_name,
        "message": f"Step '{step_name}' completed successfully (simulated).",
    }


def _validate_workflow_and_config(
    db: Session,
    workflow_id: UUID,
    request: ExecutionRequest,
) -> WorkflowInstance:
    """
    Validates that:
    1. The workflow exists (with steps eagerly loaded).
    2. If failure_simulation is specified, the fail_at_step_order refers
       to an actual step in the workflow.

    This runs in a read-only query BEFORE any execution record is created,
    so invalid requests never create side effects.

    Returns the WorkflowInstance with steps loaded.
    Raises WorkflowNotFoundError or InvalidFailureConfigError on failure.
    """
    stmt = (
        select(WorkflowInstance)
        .options(selectinload(WorkflowInstance.steps))
        .where(WorkflowInstance.id == workflow_id)
    )
    workflow = db.execute(stmt).scalar_one_or_none()

    if workflow is None:
        raise WorkflowNotFoundError(
            f"Workflow with ID '{workflow_id}' not found."
        )

    # Validate failure injection target
    if request.failure_simulation is not None:
        target_order = request.failure_simulation.fail_at_step_order
        step_orders = {step.step_order for step in workflow.steps}
        if target_order not in step_orders:
            raise InvalidFailureConfigError(
                f"Cannot inject failure at step_order={target_order}. "
                f"Workflow '{workflow.name}' has step_orders: {sorted(step_orders)}."
            )

    return workflow


def _initialise_execution(
    db: Session,
    workflow: WorkflowInstance,
    request: ExecutionRequest,
) -> WorkflowExecution:
    """
    Creates a new WorkflowExecution record with:
    - Row-level locking (SELECT ... FOR UPDATE) on the workflow row to
      serialise concurrent execution requests.
    - Safe attempt_number allocation using MAX(attempt_number) + 1.
    - Conflict detection: rejects creation if a PENDING or RUNNING
      execution already exists for this workflow.

    This is a short-lived transaction: it commits the PENDING execution
    record and returns it.

    Raises ActiveExecutionConflictError if there is already an active execution.
    """
    # Lock the workflow row to serialise concurrent attempts
    lock_stmt = (
        select(WorkflowInstance)
        .where(WorkflowInstance.id == workflow.id)
        .with_for_update()
    )
    db.execute(lock_stmt).scalar_one()

    # Check for active (PENDING or RUNNING) executions
    active_check_stmt = (
        select(func.count())
        .select_from(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_id == workflow.id,
            WorkflowExecution.status.in_([
                ExecutionStatus.PENDING.value,
                ExecutionStatus.RUNNING.value,
            ]),
        )
    )
    active_count = db.execute(active_check_stmt).scalar() or 0

    if active_count > 0:
        raise ActiveExecutionConflictError(
            f"Workflow '{workflow.name}' already has an active execution "
            f"(PENDING or RUNNING). Complete or cancel it before starting a new one."
        )

    # Determine the next attempt number
    max_attempt_stmt = (
        select(func.max(WorkflowExecution.attempt_number))
        .where(WorkflowExecution.workflow_id == workflow.id)
    )
    max_attempt = db.execute(max_attempt_stmt).scalar() or 0
    next_attempt = max_attempt + 1

    # Build the failure simulation config dict for storage
    sim_config = None
    if request.failure_simulation is not None:
        sim_config = {
            "fail_at_step_order": request.failure_simulation.fail_at_step_order,
            "error_message": request.failure_simulation.error_message,
        }

    # Create the execution record
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        attempt_number=next_attempt,
        status=ExecutionStatus.PENDING.value,
        trigger_type="SIMULATED",
        failure_simulation_config=sim_config,
    )
    db.add(execution)

    # Create execution step records from the workflow step definitions
    for step in sorted(workflow.steps, key=lambda s: s.step_order):
        exec_step = ExecutionStep(
            workflow_step_id=step.id,
            step_order=step.step_order,
            name=step.name,
            status=ExecutionStepStatus.PENDING.value,
        )
        execution.execution_steps.append(exec_step)

    try:
        db.commit()
        db.refresh(execution)
        return execution
    except Exception:
        db.rollback()
        raise


def _run_execution(
    db: Session,
    execution: WorkflowExecution,
    request: ExecutionRequest,
) -> WorkflowExecution:
    """
    Runs the execution step-by-step.

    TRANSACTION STRATEGY: Each step update is its own short-lived transaction.
    Simulated work happens OUTSIDE any open transaction, so the DB connection
    is not held idle during processing.

    On injected failure:
    - The targeted step is marked FAILED with the configured error message.
    - All subsequent steps remain PENDING (never attempted, no timestamps).
    - The execution is marked FAILED.

    On success:
    - All steps are marked COMPLETED with simulated output.
    - The execution is marked COMPLETED.
    """
    fail_at = None
    fail_msg = "Simulated failure injected by UNDOX failure simulation engine."
    if request.failure_simulation is not None:
        fail_at = request.failure_simulation.fail_at_step_order
        if request.failure_simulation.error_message:
            fail_msg = request.failure_simulation.error_message

    # --- Mark execution as RUNNING (short transaction) ---
    execution.status = ExecutionStatus.RUNNING.value
    execution.started_at = _utcnow()
    try:
        db.commit()
        db.refresh(execution)
    except Exception:
        db.rollback()
        raise

    # --- Execute steps sequentially ---
    # Re-load execution steps ordered by step_order
    steps_stmt = (
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == execution.id)
        .order_by(ExecutionStep.step_order)
    )
    exec_steps = list(db.execute(steps_stmt).scalars().all())

    failure_occurred = False

    for exec_step in exec_steps:
        if failure_occurred:
            # Leave remaining steps in their original PENDING state.
            # They were never attempted, so no status change or timestamp
            # should be applied. This matches the approved requirement:
            # unattempted steps remain PENDING with no started_at/completed_at.
            continue

        # --- Mark step as RUNNING (short transaction) ---
        exec_step.status = ExecutionStepStatus.RUNNING.value
        exec_step.started_at = _utcnow()
        try:
            db.commit()
            db.refresh(exec_step)
        except Exception:
            db.rollback()
            raise

        # --- Check for injected failure ---
        if fail_at is not None and exec_step.step_order == fail_at:
            # FAILURE: mark step as failed
            exec_step.status = ExecutionStepStatus.FAILED.value
            exec_step.completed_at = _utcnow()
            exec_step.error_message = fail_msg
            try:
                db.commit()
                db.refresh(exec_step)
            except Exception:
                db.rollback()
                raise
            failure_occurred = True
            continue

        # --- Simulate work (OUTSIDE any transaction) ---
        step_output = _simulate_step_work(exec_step.name)

        # --- Mark step as COMPLETED (short transaction) ---
        exec_step.status = ExecutionStepStatus.COMPLETED.value
        exec_step.completed_at = _utcnow()
        exec_step.step_output = step_output
        try:
            db.commit()
            db.refresh(exec_step)
        except Exception:
            db.rollback()
            raise

    # --- Mark execution as COMPLETED or FAILED (short transaction) ---
    now = _utcnow()
    if failure_occurred:
        execution.status = ExecutionStatus.FAILED.value
        execution.completed_at = now
        execution.failure_reason = (
            f"Step '{exec_steps[fail_at - 1].name}' (order={fail_at}) failed: {fail_msg}"
            if fail_at and 0 < fail_at <= len(exec_steps)
            else f"Execution failed due to injected failure."
        )
    else:
        execution.status = ExecutionStatus.COMPLETED.value
        execution.completed_at = now

    try:
        db.commit()
        db.refresh(execution)
    except Exception:
        db.rollback()
        raise

    return execution


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_workflow(
    db: Session,
    workflow_id: UUID,
    request: ExecutionRequest,
) -> WorkflowExecution:
    """
    Executes a registered workflow with optional failure injection.

    Steps:
    1. Validate the workflow exists and the failure config (if any) is valid.
    2. Initialise a new WorkflowExecution with row-level locking.
    3. Run each step sequentially with short-lived transactions.
    4. Return the completed (or failed) execution with all step states.

    Raises:
    - WorkflowNotFoundError: Workflow does not exist.
    - InvalidFailureConfigError: Failure injection targets a nonexistent step.
    - ActiveExecutionConflictError: An active execution already exists.
    """
    # Phase 1: Read-only validation (no side effects on invalid input)
    workflow = _validate_workflow_and_config(db, workflow_id, request)

    # Phase 2: Initialise execution record with locking
    execution = _initialise_execution(db, workflow, request)

    # Phase 3: Run the execution engine
    execution = _run_execution(db, execution, request)

    # Phase 4: Re-load with steps eagerly loaded for the caller
    return get_execution_by_id(db, execution.id)


def get_execution_by_id(
    db: Session,
    execution_id: UUID,
) -> Optional[WorkflowExecution]:
    """
    Retrieves a single WorkflowExecution by its UUID with execution_steps
    eagerly loaded and ordered by step_order.
    """
    stmt = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.execution_steps))
        .where(WorkflowExecution.id == execution_id)
    )
    return db.execute(stmt).scalar_one_or_none()
