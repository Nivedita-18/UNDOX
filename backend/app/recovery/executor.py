
from datetime import datetime, timezone

from ..audit.service import record_audit_event
from ..models import ExecutionStep
from .service import get_recovery_plan
from .conflicts import inspect_recovery_conflicts
from .adapters import CompensationSimulationAdapter, RetrySimulationAdapter


class RecoveryExecutionError(Exception):
    pass


def execute_recovery_plan(
    db,
    plan_id: int,
    executed_by: int | None = None
):

    plan = get_recovery_plan(db, plan_id)

    if plan.status != "APPROVED":
        raise RecoveryExecutionError(
            "Only approved recovery plans can be executed."
        )

    report = inspect_recovery_conflicts(db, plan)

    if report["conflict_count"] > 0:
        raise RecoveryExecutionError(
            "Recovery plan contains unresolved conflicts."
        )

    if (
        report["manual_review_required"]
        and not plan.review_reason
    ):
        raise RecoveryExecutionError(
            "Manual review acknowledgement is missing."
        )

    try:

        plan.status = "EXECUTING"
        plan.updated_at = datetime.now(timezone.utc)

        db.flush()

        actions = sorted(
            plan.actions,
            key=lambda item: item.action_order
        )

        for action in actions:

            if action.status != "PENDING":
                raise RecoveryExecutionError(
                    "Recovery action is not pending."
                )

            now = datetime.now(timezone.utc)

            action.status = "RUNNING"
            action.started_at = now

            db.flush()

            # Execute recovery actions through concrete compensation adapters
            step_name = None
            if action.execution_step_id is not None:
                step_record = db.get(ExecutionStep, action.execution_step_id)
                if step_record:
                    step_name = step_record.step_name

            if action.action_type == "SKIP":
                action.status = "SKIPPED"
                action.result_payload = {
                    "adapter": "SkipActionAdapter",
                    "action_type": "SKIP",
                    "message": "Step skipped as planned in recovery sequence.",
                    "step_name": step_name,
                }
            elif action.action_type == "COMPENSATE":
                compensation_result = CompensationSimulationAdapter.execute(
                    action_payload=action.payload or {},
                    step_name=step_name,
                )
                action.status = "COMPLETED"
                action.result_payload = compensation_result

                # Record individual compensation audit event
                record_audit_event(
                    db,
                    event_type="RECOVERY_COMPENSATION_EXECUTED",
                    outcome="SUCCESS",
                    message=f"Compensation executed for step '{step_name or action.action_order}'",
                    actor_id=executed_by,
                    execution_id=plan.execution_id,
                    recovery_plan_id=plan.id,
                    event_data=compensation_result,
                )
            elif action.action_type == "RETRY":
                retry_result = RetrySimulationAdapter.execute(
                    action_payload=action.payload or {},
                    step_name=step_name,
                )
                action.status = "COMPLETED"
                action.result_payload = retry_result

                # Record retry audit event
                record_audit_event(
                    db,
                    event_type="RECOVERY_RETRY_EXECUTED",
                    outcome="SUCCESS",
                    message=f"Retry executed for step '{step_name or action.action_order}'",
                    actor_id=executed_by,
                    execution_id=plan.execution_id,
                    recovery_plan_id=plan.id,
                    event_data=retry_result,
                )
            else:
                action.status = "COMPLETED"
                action.result_payload = {
                    "adapter": "ManualReviewAdapter",
                    "action_type": action.action_type,
                    "message": "Manual review action confirmed by operator.",
                    "operator_review_acknowledged": action.requires_manual_review,
                    "step_name": step_name,
                }

            action.finished_at = datetime.now(timezone.utc)

        plan.status = "COMPLETED"
        plan.updated_at = datetime.now(timezone.utc)

        # Audit recovery execution
        record_audit_event(
            db,
            event_type="RECOVERY_PLAN_EXECUTED",
            outcome="SUCCESS",
            message="Recovery plan execution completed",
            actor_id=executed_by,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            event_data={
                "action_count": len(actions),
                "status": plan.status
            }
        )

        db.commit()

        return get_recovery_plan(db, plan_id)

    except Exception:
        db.rollback()
        raise
