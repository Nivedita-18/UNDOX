"""
Recovery Execution Engine for UNDOX.

Executes approved recovery plans under controlled, simulated conditions:
1. Validates plan approval status before execution.
2. Checks conflict and staleness status via Conflict Detection Engine.
3. Enforces manual review authorization for irreversible actions.
4. Executes actions strictly in planned order (action_order).
5. Prevents duplicate concurrent or repeated executions.
6. Handles simulated action failures gracefully, halting downstream actions.
7. Preserves original WorkflowExecution and ExecutionStep history intact.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.audit.service import record_audit_event
from backend.app.models.audit import AuditEventType, AuditOutcome
from backend.app.models.recovery import (
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from backend.app.models.workflow import WorkflowStatus
from backend.app.recovery.conflicts import detect_recovery_conflicts
from backend.app.recovery.service import (
    RecoveryPlanDuplicateDecisionError,
    RecoveryPlanExecutionConflictError,
    RecoveryPlanNotApprovedError,
    RecoveryPlanNotFoundError,
    RecoveryPlanStaleError,
    RecoveryPlanUnauthorizedActionError,
    get_recovery_plan_by_id,
)
from backend.app.schemas.recovery import (
    ConflictSeverity,
    ConflictType,
    RecoveryExecutionRequest,
    RecoveryExecutionStatusResponse,
    RecoveryPlanActionResponse,
    RecoveryPlanApprovalRequest,
    RecoveryPlanRejectionRequest,
)


def record_plan_decision(
    plan: RecoveryPlan,
    decision: str,
    operator: str,
    reason: str,
) -> None:
    """
    Appends structured operator decision and audit metadata to the plan summary.
    """
    now = datetime.now(timezone.utc)
    plan.status = decision
    plan.updated_at = now
    audit_marker = "\n\n--- Operator Decision ---\n"
    clean_summary = (plan.summary or "").split("--- Operator Decision ---")[0].rstrip()
    plan.summary = (
        f"{clean_summary}{audit_marker}"
        f"Decision: {decision}\n"
        f"Operator: {operator}\n"
        f"Timestamp: {now.isoformat()}\n"
        f"Reason: {reason}"
    )


def approve_recovery_plan(
    db: Session,
    plan_id: UUID,
    request: Optional[RecoveryPlanApprovalRequest] = None,
) -> RecoveryPlan:
    """
    Approves a generated or pending recovery plan, authorizing it for execution.

    - Validates that the plan exists.
    - Prevents duplicate approval (raises RecoveryPlanDuplicateDecisionError if already APPROVED).
    - Prevents contradictory decisions (raises RecoveryPlanExecutionConflictError if REJECTED, EXECUTING, or COMPLETED).
    - Evaluates conflicts: auto-rejects and blocks approval if plan is stale or has unresolved blocking conflicts.
    - If the plan contains irreversible actions or requires manual review, requires
      explicit authorization (authorize_manual_review=True).
    - Records the decision, operator, and reason into the audit trail.
    - Transitions plan status to APPROVED.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if plan is None:
        raise RecoveryPlanNotFoundError(
            f"Recovery plan with ID '{plan_id}' not found."
        )

    # Prevent duplicate approval decisions
    if plan.status == RecoveryPlanStatus.APPROVED.value:
        raise RecoveryPlanDuplicateDecisionError(
            f"Recovery plan '{plan_id}' has already been approved."
        )

    # Prevent contradictory decisions on terminal or active plans
    if plan.status == RecoveryPlanStatus.REJECTED.value:
        raise RecoveryPlanExecutionConflictError(
            f"Cannot approve recovery plan '{plan_id}' because it has already been rejected."
        )
    if plan.status in (
        RecoveryPlanStatus.COMPLETED.value,
        RecoveryPlanStatus.EXECUTING.value,
        RecoveryPlanStatus.FAILED.value,
    ):
        raise RecoveryPlanExecutionConflictError(
            f"Cannot approve recovery plan '{plan_id}' because it has status '{plan.status}'."
        )

    req = request or RecoveryPlanApprovalRequest()
    operator = req.operator or "operator"

    # Conflict and staleness pre-check
    conflict_report = detect_recovery_conflicts(db, plan_id)

    # 1. Active concurrency conflict (another plan executing/approved)
    active_conflict = next(
        (c for c in conflict_report.conflicts if c.conflict_type == ConflictType.ACTIVE_PLAN_CONCURRENCY.value),
        None,
    )
    if active_conflict:
        conflict_reason = f"Auto-rejected during approval evaluation: Unresolved blocking conflict ({active_conflict.message})."
        record_plan_decision(plan, RecoveryPlanStatus.REJECTED.value, operator, conflict_reason)
        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_PLAN_REJECTED,
            outcome=AuditOutcome.REJECTED,
            message=conflict_reason,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            actor=operator,
            details={"auto_rejected": True, "conflict_type": active_conflict.conflict_type, "reason": conflict_reason},
            commit=False,
        )
        db.commit()
        raise RecoveryPlanExecutionConflictError(
            f"Cannot approve recovery plan '{plan_id}' due to unresolved blocking conflict: {active_conflict.message}. "
            f"The plan has been marked REJECTED."
        )

    # 2. Plan staleness check
    if conflict_report.is_stale:
        stale_reason = (
            "Auto-rejected during approval evaluation: Plan is stale. The underlying execution "
            "state or workflow has changed since plan generation."
        )
        record_plan_decision(plan, RecoveryPlanStatus.REJECTED.value, operator, stale_reason)
        stale_msgs = [c.message for c in conflict_report.conflicts if "stale" in c.conflict_type.lower()]
        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_PLAN_REJECTED,
            outcome=AuditOutcome.REJECTED,
            message=stale_reason,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            actor=operator,
            details={"auto_rejected": True, "is_stale": True, "reasons": stale_msgs},
            commit=False,
        )
        db.commit()
        raise RecoveryPlanStaleError(
            f"Cannot approve stale recovery plan '{plan_id}'. The underlying execution state "
            f"or workflow has changed since plan generation. The plan has been marked REJECTED."
        )

    # 3. Other critical unresolved conflicts
    if conflict_report.highest_severity == ConflictSeverity.CRITICAL.value:
        crit_msg = next(
            (c.message for c in conflict_report.conflicts if c.severity == ConflictSeverity.CRITICAL.value),
            "Critical conflict detected",
        )
        conflict_reason = f"Auto-rejected during approval evaluation: Unresolved blocking conflict ({crit_msg})."
        record_plan_decision(plan, RecoveryPlanStatus.REJECTED.value, operator, conflict_reason)
        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_PLAN_REJECTED,
            outcome=AuditOutcome.REJECTED,
            message=conflict_reason,
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            actor=operator,
            details={"auto_rejected": True, "conflict_severity": "CRITICAL", "reason": conflict_reason},
            commit=False,
        )
        db.commit()
        raise RecoveryPlanExecutionConflictError(
            f"Cannot approve recovery plan '{plan_id}' due to unresolved blocking conflict: {crit_msg}. "
            f"The plan has been marked REJECTED."
        )

    # Manual review authorization check
    if conflict_report.requires_manual_approval and not req.authorize_manual_review:
        raise RecoveryPlanUnauthorizedActionError(
            f"Recovery plan '{plan_id}' contains actions requiring manual review or irreversible "
            f"side-effects. Explicit authorization required (set 'authorize_manual_review=True')."
        )

    # If authorized, mark manual review actions as proposed/ready
    if req.authorize_manual_review:
        plan.requires_manual_approval = False
        for action in plan.actions:
            if action.status == RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value:
                action.status = RecoveryActionStatus.PROPOSED.value

    approval_reason = req.reason or req.notes or "Approved by operator"
    record_plan_decision(plan, RecoveryPlanStatus.APPROVED.value, operator, approval_reason)
    record_audit_event(
        db=db,
        event_type=AuditEventType.RECOVERY_PLAN_APPROVED,
        outcome=AuditOutcome.APPROVED,
        message=f"Recovery plan approved by {operator}: {approval_reason}",
        execution_id=plan.execution_id,
        recovery_plan_id=plan.id,
        actor=operator,
        details={"operator": operator, "reason": approval_reason, "authorize_manual_review": req.authorize_manual_review},
        commit=False,
    )

    db.commit()
    db.refresh(plan)
    return get_recovery_plan_by_id(db, plan.id)


def reject_recovery_plan(
    db: Session,
    plan_id: UUID,
    request: Optional[RecoveryPlanRejectionRequest] = None,
    notes: Optional[str] = None,
) -> RecoveryPlan:
    """
    Rejects a recovery plan, preventing its execution.

    - Validates that the plan exists.
    - Prevents duplicate rejection (raises RecoveryPlanDuplicateDecisionError if already REJECTED).
    - Prevents contradictory decisions (raises RecoveryPlanExecutionConflictError if APPROVED, EXECUTING, or COMPLETED).
    - Records the decision, operator, and rejection reason.
    - Transitions plan status to REJECTED.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if plan is None:
        raise RecoveryPlanNotFoundError(
            f"Recovery plan with ID '{plan_id}' not found."
        )

    # Prevent duplicate rejection decisions
    if plan.status == RecoveryPlanStatus.REJECTED.value:
        raise RecoveryPlanDuplicateDecisionError(
            f"Recovery plan '{plan_id}' has already been rejected."
        )

    # Prevent contradictory decisions on approved or active plans
    if plan.status == RecoveryPlanStatus.APPROVED.value:
        raise RecoveryPlanExecutionConflictError(
            f"Cannot reject recovery plan '{plan_id}' because it has already been approved."
        )
    if plan.status in (
        RecoveryPlanStatus.COMPLETED.value,
        RecoveryPlanStatus.EXECUTING.value,
        RecoveryPlanStatus.FAILED.value,
    ):
        raise RecoveryPlanExecutionConflictError(
            f"Cannot reject recovery plan '{plan_id}' because it has status '{plan.status}'."
        )

    req = request or RecoveryPlanRejectionRequest()
    rejection_reason = notes or req.reason or "Rejected by operator"
    operator = req.operator or "operator"

    record_plan_decision(plan, RecoveryPlanStatus.REJECTED.value, operator, rejection_reason)
    record_audit_event(
        db=db,
        event_type=AuditEventType.RECOVERY_PLAN_REJECTED,
        outcome=AuditOutcome.REJECTED,
        message=f"Recovery plan rejected by {operator}: {rejection_reason}",
        execution_id=plan.execution_id,
        recovery_plan_id=plan.id,
        actor=operator,
        details={"operator": operator, "reason": rejection_reason},
        commit=False,
    )

    db.commit()
    db.refresh(plan)
    return get_recovery_plan_by_id(db, plan.id)


def execute_recovery_plan(
    db: Session,
    plan_id: UUID,
    request: Optional[RecoveryExecutionRequest] = None,
) -> RecoveryPlan:
    """
    Executes an approved recovery plan using simulated actions in strict action_order.

    Requirements enforced:
    1. Plan must exist (raises RecoveryPlanNotFoundError if missing).
    2. Plan must not be currently executing or already completed (raises RecoveryPlanExecutionConflictError).
    3. Plan must be in APPROVED status (raises RecoveryPlanNotApprovedError).
    4. Plan must not be stale or have critical conflicts (raises RecoveryPlanStaleError / RecoveryPlanExecutionConflictError).
    5. Irreversible/manual review actions must not remain unauthorized (raises RecoveryPlanUnauthorizedActionError).
    6. Actions are executed in order defined by action_order.
    7. Supports action failure simulation: halts downstream actions safely.
    8. Preserves original WorkflowExecution and ExecutionStep history intact.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if plan is None:
        raise RecoveryPlanNotFoundError(
            f"Recovery plan with ID '{plan_id}' not found."
        )

    # 1. Prevent duplicate execution
    if plan.status == RecoveryPlanStatus.EXECUTING.value:
        raise RecoveryPlanExecutionConflictError(
            f"Recovery plan '{plan_id}' is already actively executing."
        )
    if plan.status == RecoveryPlanStatus.COMPLETED.value:
        raise RecoveryPlanExecutionConflictError(
            f"Recovery plan '{plan_id}' has already been executed and completed."
        )

    # 2. Enforce approval
    if plan.status == RecoveryPlanStatus.REJECTED.value:
        reason_info = f" (Reason: '{plan.decision_reason}')" if plan.decision_reason else ""
        raise RecoveryPlanNotApprovedError(
            f"Cannot execute recovery plan '{plan_id}' because it was REJECTED{reason_info}. "
            f"Only plans in '{RecoveryPlanStatus.APPROVED.value}' status can be executed."
        )

    if plan.status != RecoveryPlanStatus.APPROVED.value:
        raise RecoveryPlanNotApprovedError(
            f"Cannot execute recovery plan '{plan_id}' in '{plan.status}' status. "
            f"Only plans in '{RecoveryPlanStatus.APPROVED.value}' status can be executed."
        )

    # 3. Conflict and staleness pre-check
    conflict_report = detect_recovery_conflicts(db, plan_id)
    if conflict_report.is_stale:
        raise RecoveryPlanStaleError(
            f"Cannot execute recovery plan '{plan_id}': plan has become stale since approval."
        )
    if conflict_report.highest_severity == ConflictSeverity.CRITICAL.value:
        crit_msg = next(
            (c.message for c in conflict_report.conflicts if c.severity == ConflictSeverity.CRITICAL.value),
            "Critical conflict detected",
        )
        raise RecoveryPlanExecutionConflictError(
            f"Cannot execute recovery plan '{plan_id}' due to critical conflict: {crit_msg}"
        )

    # 4. Check for unauthorized manual review actions
    for action in plan.actions:
        if action.status == RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value:
            raise RecoveryPlanUnauthorizedActionError(
                f"Action {action.action_order} ('{action.target_step_name}') requires manual review "
                f"and has not been authorized."
            )

    req = request or RecoveryExecutionRequest()

    # 5. Begin execution: transition plan status to EXECUTING
    plan.status = RecoveryPlanStatus.EXECUTING.value
    plan.updated_at = datetime.now(timezone.utc)
    db.commit()

    sorted_actions = sorted(plan.actions, key=lambda a: a.action_order)

    record_audit_event(
        db=db,
        event_type=AuditEventType.RECOVERY_EXECUTION_STARTED,
        outcome=AuditOutcome.STARTED,
        message=f"Started execution of recovery plan '{plan.id}' with {len(sorted_actions)} actions.",
        execution_id=plan.execution_id,
        recovery_plan_id=plan.id,
        actor="system",
        details={"action_count": len(sorted_actions)},
    )

    failed_any = False

    # 6. Execute actions sequentially in defined action_order
    for idx, action in enumerate(sorted_actions):
        action.status = RecoveryActionStatus.EXECUTING.value
        db.commit()

        # Simulated failure check
        if req.simulate_action_failure_at_order == action.action_order:
            failed_any = True
            action.status = RecoveryActionStatus.FAILED.value
            details = dict(action.compensation_details or {})
            details["execution_result"] = {
                "status": "FAILED",
                "simulated": True,
                "error": req.simulated_error_message,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            action.compensation_details = details
            db.commit()

            # Skip remaining downstream actions
            for remaining in sorted_actions[idx + 1:]:
                remaining.status = RecoveryActionStatus.SKIPPED.value
                rem_details = dict(remaining.compensation_details or {})
                rem_details["execution_result"] = {
                    "status": "SKIPPED",
                    "reason": f"Skipped due to failure at action {action.action_order}",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
                remaining.compensation_details = rem_details
            break
        else:
            # Action executed successfully (simulated)
            action.status = RecoveryActionStatus.COMPLETED.value
            details = dict(action.compensation_details or {})
            details["execution_result"] = {
                "status": "COMPLETED",
                "simulated": True,
                "message": (
                    f"Successfully executed simulated recovery action '{action.action_type}' "
                    f"for step '{action.target_step_name}'."
                ),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            action.compensation_details = details
            db.commit()

    # 7. Finalize recovery plan status
    if failed_any:
        plan.status = RecoveryPlanStatus.FAILED.value
        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_EXECUTION_FAILED,
            outcome=AuditOutcome.FAILED,
            message=(
                f"Recovery plan execution failed at action order {req.simulate_action_failure_at_order}: "
                f"{req.simulated_error_message or 'Simulated failure'}"
            ),
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            actor="system",
            details={
                "failed_action_order": req.simulate_action_failure_at_order,
                "error": req.simulated_error_message,
            },
            commit=False,
        )
    else:
        plan.status = RecoveryPlanStatus.COMPLETED.value
        # Reconcile parent workflow status to RECOVERED if all actions finished cleanly
        if plan.workflow:
            plan.workflow.status = WorkflowStatus.RECOVERED.value
        record_audit_event(
            db=db,
            event_type=AuditEventType.RECOVERY_EXECUTION_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            message=f"Recovery plan execution completed successfully. All {len(sorted_actions)} actions succeeded.",
            execution_id=plan.execution_id,
            recovery_plan_id=plan.id,
            actor="system",
            details={"action_count": len(sorted_actions)},
            commit=False,
        )

    plan.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(plan)

    return get_recovery_plan_by_id(db, plan.id)


def get_recovery_execution_status(
    db: Session,
    plan_id: UUID,
) -> RecoveryExecutionStatusResponse:
    """
    Retrieves runtime execution status and progress summary for a recovery plan.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if plan is None:
        raise RecoveryPlanNotFoundError(
            f"Recovery plan with ID '{plan_id}' not found."
        )

    total_actions = len(plan.actions)
    completed_actions = sum(
        1 for a in plan.actions if a.status == RecoveryActionStatus.COMPLETED.value
    )
    failed_actions = sum(
        1 for a in plan.actions if a.status == RecoveryActionStatus.FAILED.value
    )
    pending_actions = total_actions - completed_actions - failed_actions

    return RecoveryExecutionStatusResponse(
        plan_id=plan.id,
        execution_id=plan.execution_id,
        workflow_id=plan.workflow_id,
        status=plan.status,
        strategy=plan.strategy,
        requires_manual_approval=plan.requires_manual_approval,
        total_actions=total_actions,
        completed_actions=completed_actions,
        failed_actions=failed_actions,
        pending_actions=pending_actions,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        actions=[RecoveryPlanActionResponse.model_validate(a) for a in plan.actions],
    )
