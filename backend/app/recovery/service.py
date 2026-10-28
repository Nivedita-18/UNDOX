"""
Failure Recovery Planning Engine service for UNDOX.

Analyzes completed, failed, and pending execution steps for a failed WorkflowExecution,
and generates an actionable, auditable RecoveryPlan with ordered proposed actions.
Preserves original execution history by keeping execution records completely immutable.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    WorkflowExecution,
)
from backend.app.models.recovery import (
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryPlan,
    RecoveryPlanAction,
    RecoveryPlanStatus,
)
from backend.app.audit.service import record_audit_event
from backend.app.models.audit import AuditEventType, AuditOutcome
from backend.app.schemas.recovery import RecoveryPlanRequest

# Step name substrings that indicate non-reversible actions by default
IRREVERSIBLE_KEYWORDS = (
    "email",
    "sms",
    "notification",
    "notify",
    "dispatch",
    "physical",
    "print",
    "wire",
    "shred",
    "destroy",
    "publish",
    "irreversible",
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class RecoveryError(Exception):
    """Base exception for recovery service errors."""
    pass


class ExecutionNotFoundError(RecoveryError):
    """Raised when the requested execution does not exist."""
    pass


class ExecutionNotFailedError(RecoveryError):
    """Raised when recovery planning is requested for an execution that is not FAILED."""
    pass


class RecoveryPlanNotFoundError(RecoveryError):
    """Raised when the requested recovery plan does not exist."""
    pass


class RecoveryPlanNotApprovedError(RecoveryError):
    """Raised when attempting to execute a recovery plan that is not in APPROVED status."""
    pass


class RecoveryPlanExecutionConflictError(RecoveryError):
    """Raised when attempting to execute a recovery plan that is already executing or completed."""
    pass


class RecoveryPlanDuplicateDecisionError(RecoveryPlanExecutionConflictError):
    """Raised when an approval or rejection decision is attempted on an already decided plan."""
    pass


class RecoveryPlanStaleError(RecoveryError):
    """Raised when attempting to execute or approve a recovery plan that has become stale."""
    pass


class RecoveryPlanUnauthorizedActionError(RecoveryError):
    """Raised when a plan contains irreversible or manual review actions without explicit authorization."""
    pass


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _is_step_reversible(
    step: ExecutionStep,
    unsupported_steps: Optional[List[int]] = None,
) -> bool:
    """
    Determines whether a completed step can be safely and automatically compensated.
    Returns False if:
    - The step's step_order is in the caller-specified unsupported_steps list, OR
    - The step's name contains keywords indicating an irreversible real-world side effect.
    """
    if unsupported_steps and step.step_order in unsupported_steps:
        return False

    name_lower = step.name.lower()
    for kw in IRREVERSIBLE_KEYWORDS:
        if kw in name_lower:
            return False

    return True


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------


def plan_recovery_for_execution(
    db: Session,
    execution_id: UUID,
    request: Optional[RecoveryPlanRequest] = None,
) -> RecoveryPlan:
    """
    Generates a persistent RecoveryPlan for an existing failed WorkflowExecution.

    Requirements enforced:
    1. Validates that the execution exists (raises ExecutionNotFoundError if missing).
    2. Validates that the execution is in FAILED status (raises ExecutionNotFailedError otherwise).
    3. Analyzes completed, failed, and pending steps.
    4. Proposes LIFO compensation for completed steps, marking unsupported/irreversible
       steps as requiring manual review.
    5. Preserves original execution history (does NOT modify WorkflowExecution or ExecutionStep).
    6. Stores the plan and ordered actions in the database.
    """
    req = request if request is not None else RecoveryPlanRequest()

    # 1. Load the execution with its steps and workflow (read-only query)
    stmt = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.execution_steps),
            selectinload(WorkflowExecution.workflow),
        )
        .where(WorkflowExecution.id == execution_id)
    )
    execution = db.execute(stmt).scalar_one_or_none()

    if execution is None:
        raise ExecutionNotFoundError(
            f"Execution with ID '{execution_id}' not found."
        )

    # 2. Verify execution is in FAILED status
    if execution.status != ExecutionStatus.FAILED.value:
        raise ExecutionNotFailedError(
            f"Cannot generate recovery plan for execution with status '{execution.status}'. "
            f"Recovery planning requires an execution in '{ExecutionStatus.FAILED.value}' status."
        )

    # 3. Categorize execution steps
    all_steps = sorted(execution.execution_steps, key=lambda s: s.step_order)
    completed_steps = [s for s in all_steps if s.status == ExecutionStepStatus.COMPLETED.value]
    failed_steps = [s for s in all_steps if s.status == ExecutionStepStatus.FAILED.value]
    pending_steps = [s for s in all_steps if s.status == ExecutionStepStatus.PENDING.value]

    failed_step = failed_steps[0] if failed_steps else None
    unsupported_steps = req.unsupported_steps or []

    # 4. Generate proposed actions
    proposed_actions: List[RecoveryPlanAction] = []
    action_counter = 1
    has_manual_review = False

    # A. Compensate completed steps in REVERSE (LIFO) order
    for step in reversed(completed_steps):
        is_reversible = _is_step_reversible(step, unsupported_steps)

        if is_reversible:
            action = RecoveryPlanAction(
                action_order=action_counter,
                target_step_order=step.step_order,
                target_execution_step_id=step.id,
                action_type=RecoveryActionType.COMPENSATE.value,
                target_step_name=step.name,
                status=RecoveryActionStatus.PROPOSED.value,
                is_reversible=True,
                explanation=(
                    f"Compensate completed step '{step.name}' (order={step.step_order}) "
                    f"via simulated reversal."
                ),
                compensation_details={
                    "simulated": True,
                    "original_step_name": step.name,
                    "action": f"Revert side-effects of step '{step.name}'",
                    "target_step_order": step.step_order,
                },
            )
        else:
            has_manual_review = True
            action = RecoveryPlanAction(
                action_order=action_counter,
                target_step_order=step.step_order,
                target_execution_step_id=step.id,
                action_type=RecoveryActionType.MANUAL_REVIEW.value,
                target_step_name=step.name,
                status=RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value,
                is_reversible=False,
                explanation=(
                    f"Step '{step.name}' (order={step.step_order}) completed before failure "
                    f"but is classified as irreversible or unsupported for automated compensation. "
                    f"Manual review required."
                ),
                compensation_details={
                    "simulated": False,
                    "reason": "Irreversible side-effect or unsupported automated compensation",
                    "target_step_order": step.step_order,
                },
            )

        proposed_actions.append(action)
        action_counter += 1

    # B. Address the failed step
    if failed_step:
        failed_action = RecoveryPlanAction(
            action_order=action_counter,
            target_step_order=failed_step.step_order,
            target_execution_step_id=failed_step.id,
            action_type=RecoveryActionType.RETRY.value,
            target_step_name=failed_step.name,
            status=RecoveryActionStatus.PROPOSED.value,
            is_reversible=True,
            explanation=(
                f"Step '{failed_step.name}' (order={failed_step.step_order}) halted with error: "
                f"'{failed_step.error_message}'. Proposed for retry after compensating preceding steps."
            ),
            compensation_details={
                "target_step_order": failed_step.step_order,
                "error_message": failed_step.error_message,
            },
        )
        proposed_actions.append(failed_action)
        action_counter += 1

    # C. Address pending unattempted steps
    for step in pending_steps:
        skip_action = RecoveryPlanAction(
            action_order=action_counter,
            target_step_order=step.step_order,
            target_execution_step_id=step.id,
            action_type=RecoveryActionType.SKIP.value,
            target_step_name=step.name,
            status=RecoveryActionStatus.PROPOSED.value,
            is_reversible=True,
            explanation=(
                f"Pending step '{step.name}' (order={step.step_order}) was never attempted; "
                f"no compensation required."
            ),
            compensation_details={
                "target_step_order": step.step_order,
            },
        )
        proposed_actions.append(skip_action)
        action_counter += 1

    # 5. Formulate plan strategy and summary
    if has_manual_review:
        strategy = req.strategy or "MANUAL_REVIEW"
        requires_manual_approval = True
        summary = (
            f"Recovery plan requires manual review. Execution halted at step "
            f"{failed_step.step_order if failed_step else '?'} with error: "
            f"'{failed_step.error_message if failed_step else 'None'}'. "
            f"One or more completed steps cannot be automatically reversed."
        )
    else:
        strategy = req.strategy or "SAGA_COMPENSATE"
        requires_manual_approval = False
        summary = (
            f"Automated compensation plan. Execution halted at step "
            f"{failed_step.step_order if failed_step else '?'} with error: "
            f"'{failed_step.error_message if failed_step else 'None'}'. "
            f"All {len(completed_steps)} completed step(s) can be safely compensated in reverse order."
        )

    # 6. Create and persist the RecoveryPlan
    plan = RecoveryPlan(
        execution_id=execution.id,
        workflow_id=execution.workflow_id,
        status=RecoveryPlanStatus.GENERATED.value,
        strategy=strategy,
        summary=summary,
        requires_manual_approval=requires_manual_approval,
    )
    plan.actions = proposed_actions

    try:
        db.add(plan)
        db.commit()
        db.refresh(plan)

        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_PLAN_CREATED,
            outcome=AuditOutcome.SUCCESS,
            message=(
                f"Recovery plan created with strategy '{strategy}' containing {len(proposed_actions)} actions "
                f"(requires_manual_approval={requires_manual_approval})."
            ),
            execution_id=execution.id,
            recovery_plan_id=plan.id,
            actor="system",
            details={
                "strategy": strategy,
                "action_count": len(proposed_actions),
                "requires_manual_approval": requires_manual_approval,
            },
        )

        return get_recovery_plan_by_id(db, plan.id)
    except Exception:
        db.rollback()
        raise


def get_recovery_plan_by_id(
    db: Session,
    plan_id: UUID,
) -> Optional[RecoveryPlan]:
    """
    Retrieves a RecoveryPlan by its UUID with all actions eagerly loaded.
    """
    stmt = (
        select(RecoveryPlan)
        .options(selectinload(RecoveryPlan.actions))
        .where(RecoveryPlan.id == plan_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_recovery_plans_for_execution(
    db: Session,
    execution_id: UUID,
) -> List[RecoveryPlan]:
    """
    Retrieves all recovery plans generated for a specific execution,
    ordered newest first with actions eagerly loaded.
    Raises ExecutionNotFoundError if the execution does not exist.
    """
    execution = db.get(WorkflowExecution, execution_id)
    if not execution:
        raise ExecutionNotFoundError(f"Execution with ID '{execution_id}' not found.")

    stmt = (
        select(RecoveryPlan)
        .options(selectinload(RecoveryPlan.actions))
        .where(RecoveryPlan.execution_id == execution_id)
        .order_by(RecoveryPlan.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
 
 
# Alias for backwards/test compatibility
generate_recovery_plan = plan_recovery_for_execution

