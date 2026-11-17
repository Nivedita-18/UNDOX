
from datetime import datetime, timezone

from ..audit.service import record_audit_event

from .service import get_recovery_plan
from .conflicts import inspect_recovery_conflicts


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

            # Recovery actions are currently simulated.
            # Real external services are not connected.

            if action.action_type == "SKIP":

                action.status = "SKIPPED"

            else:

                action.status = "COMPLETED"

            action.result_payload = {
                "simulated": True,
                "action_type": action.action_type,
                "message": (
                    "Recovery action simulated successfully"
                ),
                "operator_review_acknowledged": (
                    action.requires_manual_review
                )
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
