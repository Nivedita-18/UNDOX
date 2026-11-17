
from sqlalchemy.orm import Session

from ..models import ExecutionStep


# Inspect recovery plan for conflicts and stale data
def inspect_recovery_conflicts(
    db: Session,
    plan
):

    conflicts = []
    manual_review = []

    execution = plan.execution

    # Check original execution availability
    if execution is None:

        conflicts.append({
            "type": "MISSING_EXECUTION",
            "message": "Original workflow execution was not found."
        })

    else:

        # Recovery is allowed only for failed executions
        if execution.status != "FAILED":

            conflicts.append({
                "type": "STALE_EXECUTION",
                "message": (
                    "Original execution is no longer in FAILED state."
                )
            })

    # Check if recovery plan contains actions
    if not plan.actions:

        conflicts.append({
            "type": "EMPTY_PLAN",
            "message": "Recovery plan contains no actions."
        })

    # Check duplicate action order
    action_orders = [
        action.action_order
        for action in plan.actions
    ]

    if len(action_orders) != len(set(action_orders)):

        conflicts.append({
            "type": "DUPLICATE_ORDER",
            "message": "Duplicate recovery action order detected."
        })

    # Supported recovery action types
    allowed_action_types = {
        "COMPENSATE",
        "RETRY",
        "SKIP",
        "MANUAL_REVIEW"
    }

    # Supported action statuses
    allowed_statuses = {
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "SKIPPED"
    }

    # Inspect individual recovery actions
    for action in plan.actions:

        # Validate action order
        if action.action_order <= 0:

            conflicts.append({
                "type": "INVALID_ACTION_ORDER",
                "action_id": action.id,
                "message": "Recovery action order must be positive."
            })

        # Validate action type
        if action.action_type not in allowed_action_types:

            conflicts.append({
                "type": "INVALID_ACTION_TYPE",
                "action_id": action.id,
                "message": "Unsupported recovery action type."
            })

        # Validate action status
        if action.status not in allowed_statuses:

            conflicts.append({
                "type": "INVALID_ACTION_STATUS",
                "action_id": action.id,
                "message": "Invalid recovery action status."
            })

        # Check referenced execution step
        if action.execution_step_id is not None:

            execution_step = db.get(
                ExecutionStep,
                action.execution_step_id
            )

            if execution_step is None:

                conflicts.append({
                    "type": "MISSING_EXECUTION_STEP",
                    "action_id": action.id,
                    "message": (
                        "Recovery action references "
                        "a missing execution step."
                    )
                })

            elif (
                execution is not None
                and execution_step.execution_id != execution.id
            ):

                conflicts.append({
                    "type": "EXECUTION_STEP_MISMATCH",
                    "action_id": action.id,
                    "message": (
                        "Recovery action references a step "
                        "from another execution."
                    )
                })

        # Collect manual review requirements
        if action.requires_manual_review:

            manual_review.append({
                "action_id": action.id,
                "action_type": action.action_type,
                "description": action.description
            })

    # Prepare conflict report
    return {
        "is_stale": (
            execution is None
            or execution.status != "FAILED"
        ),

        "conflict_count": len(conflicts),

        "conflicts": conflicts,

        "manual_review_required": manual_review,

        "can_approve": (
            len(conflicts) == 0
            and plan.status in ("GENERATED", "PENDING")
        )
    }
