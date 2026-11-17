
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import (
    WorkflowExecution,
    WorkflowStep,
    RecoveryPlan,
    RecoveryPlanAction
)

from ..audit.service import record_audit_event

from .conflicts import inspect_recovery_conflicts


class RecoveryNotFoundError(Exception):
    pass


class InvalidRecoveryStateError(Exception):
    pass


class RecoveryConflictError(Exception):
    pass


class ManualReviewRequiredError(Exception):
    pass


# Load recovery plan with related records
def load_plan(db, plan_id):

    statement = (
        select(RecoveryPlan)
        .options(
            selectinload(RecoveryPlan.actions),
            selectinload(RecoveryPlan.execution)
        )
        .where(RecoveryPlan.id == plan_id)
    )

    return db.scalar(statement)


# Generate recovery plan for a failed execution
def generate_recovery_plan(
    db,
    execution_id,
    created_by=None
):

    execution = db.scalar(
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.steps)
        )
        .where(WorkflowExecution.id == execution_id)
    )

    if execution is None:
        raise RecoveryNotFoundError(
            "Execution not found"
        )

    if execution.status != "FAILED":
        raise InvalidRecoveryStateError(
            "Recovery plans can only be generated for failed executions."
        )

    try:

        plan = RecoveryPlan(
            execution_id=execution.id,
            status="GENERATED",
            description="Automatically generated recovery plan",
            conflict_count=0,
            created_by=created_by
        )

        db.add(plan)
        db.flush()

        # Reverse execution order
        ordered_steps = sorted(
            execution.steps,
            key=lambda item: item.step_order,
            reverse=True
        )

        for index, executed_step in enumerate(
            ordered_steps,
            start=1
        ):

            action_type = None
            payload = {}
            requires_manual_review = False

            workflow_step = None

            if executed_step.workflow_step_id:

                workflow_step = db.get(
                    WorkflowStep,
                    executed_step.workflow_step_id
                )

            if executed_step.status == "SKIPPED":

                action_type = "SKIP"

            elif executed_step.status == "FAILED":

                action_type = "RETRY"

                payload = dict(
                    executed_step.input_payload or {}
                )

                requires_manual_review = True

            elif executed_step.status == "COMPLETED":

                if (
                    workflow_step is not None
                    and workflow_step.is_reversible
                    and workflow_step.compensation_payload is not None
                ):

                    action_type = "COMPENSATE"

                    payload = dict(
                        workflow_step.compensation_payload
                    )

                else:

                    action_type = "MANUAL_REVIEW"

                    payload = dict(
                        executed_step.input_payload or {}
                    )

                    requires_manual_review = True

            if action_type is None:
                continue

            action = RecoveryPlanAction(
                recovery_plan_id=plan.id,
                execution_step_id=executed_step.id,
                action_order=index,
                action_type=action_type,
                description=(
                    f"{action_type} action for "
                    f"{executed_step.step_name}"
                ),
                payload=payload,
                requires_manual_review=requires_manual_review,
                status="PENDING"
            )

            db.add(action)

        plan_id = plan.id

        # Record recovery generation audit event
        record_audit_event(
            db,
            event_type="RECOVERY_PLAN_GENERATED",
            outcome="SUCCESS",
            message="Recovery plan generated successfully",
            actor_id=created_by,
            execution_id=execution.id,
            recovery_plan_id=plan_id,
            event_data={
                "execution_id": execution.id,
                "recovery_plan_id": plan_id
            }
        )

        db.commit()

        return load_plan(db, plan_id)

    except Exception:
        db.rollback()
        raise


# List recovery plans for an execution
def list_recovery_plans(db, execution_id):

    execution = db.get(
        WorkflowExecution,
        execution_id
    )

    if execution is None:
        raise RecoveryNotFoundError(
            "Execution not found"
        )

    statement = (
        select(RecoveryPlan)
        .options(
            selectinload(RecoveryPlan.actions),
            selectinload(RecoveryPlan.execution)
        )
        .where(
            RecoveryPlan.execution_id == execution_id
        )
        .order_by(RecoveryPlan.id.desc())
    )

    return list(db.scalars(statement).all())


# Retrieve individual recovery plan
def get_recovery_plan(db, plan_id):

    plan = load_plan(db, plan_id)

    if plan is None:
        raise RecoveryNotFoundError(
            "Recovery plan not found"
        )

    return plan


# Inspect recovery plan conflicts
def check_plan_conflicts(db, plan_id):

    plan = get_recovery_plan(db, plan_id)

    report = inspect_recovery_conflicts(
        db,
        plan
    )

    plan.conflict_count = report["conflict_count"]
    plan.conflict_report = report

    db.commit()

    return report


# Approve recovery plan
def approve_recovery_plan(
    db,
    plan_id,
    reason,
    manual_review_acknowledged,
    reviewer_id=None
):

    plan = get_recovery_plan(
        db,
        plan_id
    )

    if plan.status not in ("GENERATED", "PENDING"):

        raise InvalidRecoveryStateError(
            "This recovery plan cannot be approved in its current state."
        )

    report = inspect_recovery_conflicts(
        db,
        plan
    )

    if report["conflict_count"] > 0:

        raise RecoveryConflictError(
            "Resolve recovery conflicts before approval."
        )

    if (
        report["manual_review_required"]
        and not manual_review_acknowledged
    ):

        raise ManualReviewRequiredError(
            "Manual review acknowledgement is required."
        )

    try:

        plan.status = "APPROVED"
        plan.reviewed_by = reviewer_id
        plan.review_reason = reason
        plan.conflict_count = 0
        plan.conflict_report = report
        plan.updated_at = datetime.now(timezone.utc)

        # Record approval audit event
        record_audit_event(
            db,
            event_type="RECOVERY_PLAN_APPROVED",
            outcome="SUCCESS",
            message="Recovery plan approved",
            actor_id=reviewer_id,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            event_data={
                "recovery_plan_id": plan.id,
                "review_reason": reason
            }
        )

        db.commit()

        return get_recovery_plan(
            db,
            plan_id
        )

    except Exception:
        db.rollback()
        raise


# Reject recovery plan
def reject_recovery_plan(
    db,
    plan_id,
    reason,
    reviewer_id=None
):

    plan = get_recovery_plan(
        db,
        plan_id
    )

    if plan.status not in ("GENERATED", "PENDING"):

        raise InvalidRecoveryStateError(
            "This recovery plan cannot be rejected in its current state."
        )

    try:

        plan.status = "REJECTED"
        plan.reviewed_by = reviewer_id
        plan.review_reason = reason
        plan.updated_at = datetime.now(timezone.utc)

        # Record rejection audit event
        record_audit_event(
            db,
            event_type="RECOVERY_PLAN_REJECTED",
            outcome="SUCCESS",
            message="Recovery plan rejected",
            actor_id=reviewer_id,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            event_data={
                "recovery_plan_id": plan.id,
                "rejection_reason": reason
            }
        )

        db.commit()

        return get_recovery_plan(
            db,
            plan_id
        )

    except Exception:
        db.rollback()
        raise


# Retrieve recovery execution status
def get_recovery_execution_status(db, plan_id):

    plan = get_recovery_plan(
        db,
        plan_id
    )

    actions = plan.actions

    return {
        "recovery_plan_id": plan.id,
        "execution_id": plan.execution_id,
        "status": plan.status,
        "total_actions": len(actions),

        "completed_actions": sum(
            action.status == "COMPLETED"
            for action in actions
        ),

        "failed_actions": sum(
            action.status == "FAILED"
            for action in actions
        ),

        "pending_actions": sum(
            action.status == "PENDING"
            for action in actions
        ),

        "actions": actions
    }
