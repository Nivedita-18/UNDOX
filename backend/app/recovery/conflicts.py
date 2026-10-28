"""
Conflict Detection Engine for UNDOX Recovery Plans.

Inspects an existing RecoveryPlan and its associated WorkflowExecution and
WorkflowInstance to detect:
1. Plan staleness: execution status transition, superseded execution attempt,
   incompatible workflow state, modified execution steps, or newer recovery plans.
2. Intra-plan action conflicts: duplicate actions for the same step, contradictory
   actions (e.g. COMPENSATE and RETRY on the same step), or LIFO compensation
   ordering violations.
3. Irreversible actions and manual review requirements: actions with irreversible
   side-effects or explicitly flagged as requiring operator manual evaluation.
4. Inter-plan concurrency conflicts: other recovery plans for the same execution
   that are currently EXECUTING or APPROVED.

This engine is strictly read-only: it performs no mutations, does not execute actions,
and does not auto-approve plans.
"""

from collections import defaultdict
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
from backend.app.models.workflow import WorkflowInstance, WorkflowStatus
from backend.app.recovery.service import (
    RecoveryPlanNotFoundError,
    get_recovery_plan_by_id,
)
from backend.app.schemas.recovery import (
    ConflictDetail,
    ConflictSeverity,
    ConflictType,
    RecoveryPlanConflictReport,
)

SEVERITY_ORDER = {
    ConflictSeverity.CRITICAL.value: 4,
    ConflictSeverity.HIGH.value: 3,
    ConflictSeverity.MEDIUM.value: 2,
    ConflictSeverity.LOW.value: 1,
}

STALE_TYPES = {
    ConflictType.STALE_PLAN_EXECUTION_STATUS_CHANGED.value,
    ConflictType.STALE_PLAN_SUPERSEDED_EXECUTION.value,
    ConflictType.STALE_PLAN_WORKFLOW_STATE_INCOMPATIBLE.value,
    ConflictType.STALE_STEP_STATE_MISMATCH.value,
    ConflictType.SUPERSEDED_BY_NEWER_PLAN.value,
}


def detect_recovery_conflicts(
    db: Session,
    plan_id: UUID,
) -> RecoveryPlanConflictReport:
    """
    Performs comprehensive conflict and staleness analysis on a persistent RecoveryPlan.

    Args:
        db: Active SQLAlchemy database session.
        plan_id: UUID of the RecoveryPlan to evaluate.

    Returns:
        RecoveryPlanConflictReport summarizing conflict count, staleness, manual review
        requirements, highest severity, and list of ConflictDetail items.

    Raises:
        RecoveryPlanNotFoundError: If no recovery plan exists with the given plan_id.
    """
    plan = get_recovery_plan_by_id(db, plan_id)
    if plan is None:
        raise RecoveryPlanNotFoundError(
            f"Recovery plan with ID '{plan_id}' not found."
        )

    conflicts: List[ConflictDetail] = []

    # 1. Fetch execution record with eager-loaded steps and workflow
    exec_stmt = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.execution_steps),
            selectinload(WorkflowExecution.workflow),
        )
        .where(WorkflowExecution.id == plan.execution_id)
    )
    execution = db.execute(exec_stmt).scalar_one_or_none()

    if execution is None:
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.STALE_PLAN_EXECUTION_STATUS_CHANGED.value,
                severity=ConflictSeverity.CRITICAL.value,
                message=(
                    f"Recovery plan is stale: associated execution record '{plan.execution_id}' "
                    f"no longer exists in the database."
                ),
            )
        )
    else:
        # A. Check execution status change
        if execution.status != ExecutionStatus.FAILED.value:
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.STALE_PLAN_EXECUTION_STATUS_CHANGED.value,
                    severity=ConflictSeverity.CRITICAL.value,
                    message=(
                        f"Recovery plan is stale: execution status changed from "
                        f"'{ExecutionStatus.FAILED.value}' to '{execution.status}'."
                    ),
                    details={
                        "expected_status": ExecutionStatus.FAILED.value,
                        "current_status": execution.status,
                    },
                )
            )

        # B. Check for superseding execution attempts for the workflow
        newer_exec_stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == plan.workflow_id,
                WorkflowExecution.attempt_number > execution.attempt_number,
            )
            .order_by(WorkflowExecution.attempt_number.desc())
        )
        superseding_exec = db.execute(newer_exec_stmt).scalars().first()
        if superseding_exec is not None:
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.STALE_PLAN_SUPERSEDED_EXECUTION.value,
                    severity=ConflictSeverity.CRITICAL.value,
                    message=(
                        f"Recovery plan is stale: execution attempt {execution.attempt_number} "
                        f"was superseded by newer execution attempt {superseding_exec.attempt_number} "
                        f"(status='{superseding_exec.status}')."
                    ),
                    details={
                        "plan_attempt": execution.attempt_number,
                        "superseding_attempt": superseding_exec.attempt_number,
                        "superseding_execution_id": str(superseding_exec.id),
                    },
                )
            )

        # C. Check parent workflow status compatibility
        if execution.workflow and execution.workflow.status in (
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.RUNNING.value,
            WorkflowStatus.RECOVERED.value,
        ):
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.STALE_PLAN_WORKFLOW_STATE_INCOMPATIBLE.value,
                    severity=ConflictSeverity.CRITICAL.value,
                    message=(
                        f"Recovery plan is stale: parent workflow '{execution.workflow.name}' "
                        f"is in active/terminal status '{execution.workflow.status}'."
                    ),
                    details={"workflow_status": execution.workflow.status},
                )
            )

        # D. Check step status mismatches against planned actions
        steps_by_order = {s.step_order: s for s in execution.execution_steps}
        for action in plan.actions:
            step = steps_by_order.get(action.target_step_order)
            if step is not None:
                if (
                    action.action_type == RecoveryActionType.COMPENSATE.value
                    and step.status != ExecutionStepStatus.COMPLETED.value
                ):
                    conflicts.append(
                        ConflictDetail(
                            conflict_type=ConflictType.STALE_STEP_STATE_MISMATCH.value,
                            severity=ConflictSeverity.HIGH.value,
                            message=(
                                f"Step '{step.name}' (order {step.step_order}) status is now "
                                f"'{step.status}', conflicting with planned COMPENSATE action."
                            ),
                            step_order=step.step_order,
                            step_name=step.name,
                            action_id=action.id,
                            details={
                                "expected_step_status": ExecutionStepStatus.COMPLETED.value,
                                "current_step_status": step.status,
                            },
                        )
                    )
                elif (
                    action.action_type == RecoveryActionType.RETRY.value
                    and step.status != ExecutionStepStatus.FAILED.value
                ):
                    conflicts.append(
                        ConflictDetail(
                            conflict_type=ConflictType.STALE_STEP_STATE_MISMATCH.value,
                            severity=ConflictSeverity.HIGH.value,
                            message=(
                                f"Step '{step.name}' (order {step.step_order}) status is now "
                                f"'{step.status}', conflicting with planned RETRY action."
                            ),
                            step_order=step.step_order,
                            step_name=step.name,
                            action_id=action.id,
                            details={
                                "expected_step_status": ExecutionStepStatus.FAILED.value,
                                "current_step_status": step.status,
                            },
                        )
                    )
                elif (
                    action.action_type == RecoveryActionType.SKIP.value
                    and step.status in (
                        ExecutionStepStatus.COMPLETED.value,
                        ExecutionStepStatus.RUNNING.value,
                    )
                ):
                    conflicts.append(
                        ConflictDetail(
                            conflict_type=ConflictType.STALE_STEP_STATE_MISMATCH.value,
                            severity=ConflictSeverity.HIGH.value,
                            message=(
                                f"Step '{step.name}' (order {step.step_order}) status is now "
                                f"'{step.status}', conflicting with planned SKIP action."
                            ),
                            step_order=step.step_order,
                            step_name=step.name,
                            action_id=action.id,
                            details={
                                "expected_step_status": ExecutionStepStatus.PENDING.value,
                                "current_step_status": step.status,
                            },
                        )
                    )

    # 2. Check for newer recovery plans for this execution
    newer_plan_stmt = (
        select(RecoveryPlan)
        .where(
            RecoveryPlan.execution_id == plan.execution_id,
            RecoveryPlan.id != plan.id,
            RecoveryPlan.created_at > plan.created_at,
        )
        .order_by(RecoveryPlan.created_at.desc())
    )
    newer_plan = db.execute(newer_plan_stmt).scalars().first()
    if newer_plan is not None:
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.SUPERSEDED_BY_NEWER_PLAN.value,
                severity=ConflictSeverity.MEDIUM.value,
                message=(
                    f"A newer recovery plan ({newer_plan.id}) was generated after this plan."
                ),
                details={
                    "newer_plan_id": str(newer_plan.id),
                    "newer_plan_strategy": newer_plan.strategy,
                },
            )
        )

    # 3. Check for concurrent active recovery plans (EXECUTING or APPROVED)
    active_plan_stmt = (
        select(RecoveryPlan)
        .where(
            RecoveryPlan.execution_id == plan.execution_id,
            RecoveryPlan.id != plan.id,
            RecoveryPlan.status.in_([
                RecoveryPlanStatus.EXECUTING.value,
                RecoveryPlanStatus.APPROVED.value,
            ]),
        )
    )
    active_plans = db.execute(active_plan_stmt).scalars().all()
    for ap in active_plans:
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.ACTIVE_PLAN_CONCURRENCY.value,
                severity=ConflictSeverity.CRITICAL.value,
                message=(
                    f"Conflicting active recovery plan detected: Plan '{ap.id}' for this execution "
                    f"is currently in '{ap.status}' status."
                ),
                details={
                    "active_plan_id": str(ap.id),
                    "active_plan_status": ap.status,
                },
            )
        )

    # 4. Intra-Plan Action Conflicts
    actions_by_step = defaultdict(list)
    for action in plan.actions:
        actions_by_step[action.target_step_order].append(action)

    for step_order, actions in sorted(actions_by_step.items()):
        if len(actions) > 1:
            types = [a.action_type for a in actions]
            step_name = actions[0].target_step_name
            if len(set(types)) > 1:
                conflicts.append(
                    ConflictDetail(
                        conflict_type=ConflictType.CONTRADICTORY_ACTIONS.value,
                        severity=ConflictSeverity.HIGH.value,
                        message=(
                            f"Step {step_order} ('{step_name}') has multiple contradictory "
                            f"recovery actions planned: {', '.join(types)}."
                        ),
                        step_order=step_order,
                        step_name=step_name,
                        details={
                            "action_ids": [str(a.id) for a in actions],
                            "action_types": types,
                        },
                    )
                )
            else:
                conflicts.append(
                    ConflictDetail(
                        conflict_type=ConflictType.DUPLICATE_ACTION.value,
                        severity=ConflictSeverity.HIGH.value,
                        message=(
                            f"Step {step_order} ('{step_name}') has {len(actions)} duplicate "
                            f"'{types[0]}' actions."
                        ),
                        step_order=step_order,
                        step_name=step_name,
                        details={
                            "action_ids": [str(a.id) for a in actions],
                            "action_type": types[0],
                        },
                    )
                )

    # 5. Check LIFO Ordering for Compensating Actions
    compensate_actions = [
        a
        for a in sorted(plan.actions, key=lambda x: x.action_order)
        if a.action_type == RecoveryActionType.COMPENSATE.value
    ]
    for i in range(len(compensate_actions) - 1):
        curr_act = compensate_actions[i]
        next_act = compensate_actions[i + 1]
        if curr_act.target_step_order <= next_act.target_step_order:
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.ORDERING_CONFLICT.value,
                    severity=ConflictSeverity.HIGH.value,
                    message=(
                        f"Saga compensation ordering violation: Action {curr_act.action_order} "
                        f"(Step {curr_act.target_step_order}) is scheduled before "
                        f"Action {next_act.action_order} (Step {next_act.target_step_order}), "
                        f"violating LIFO reverse order."
                    ),
                    step_order=curr_act.target_step_order,
                    step_name=curr_act.target_step_name,
                    action_id=curr_act.id,
                    details={
                        "current_action_order": curr_act.action_order,
                        "current_step_order": curr_act.target_step_order,
                        "next_action_order": next_act.action_order,
                        "next_step_order": next_act.target_step_order,
                    },
                )
            )

    # 6. Irreversible Actions & Manual Review Flagging
    for action in plan.actions:
        is_irreversible = (
            not action.is_reversible
            or action.action_type == RecoveryActionType.MANUAL_REVIEW.value
            or action.status == RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value
        )
        if is_irreversible:
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.IRREVERSIBLE_ACTION.value,
                    severity=ConflictSeverity.MEDIUM.value,
                    message=(
                        f"Step {action.target_step_order} ('{action.target_step_name}') has "
                        f"irreversible side effects or is unsupported for automated compensation, "
                        f"requiring manual operator evaluation."
                    ),
                    step_order=action.target_step_order,
                    step_name=action.target_step_name,
                    action_id=action.id,
                    details={
                        "action_type": action.action_type,
                        "action_status": action.status,
                        "explanation": action.explanation,
                    },
                )
            )

    if plan.requires_manual_approval:
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.MANUAL_APPROVAL_REQUIRED.value,
                severity=ConflictSeverity.MEDIUM.value,
                message=(
                    f"Recovery plan strategy '{plan.strategy}' is flagged as requiring "
                    f"manual approval before execution can proceed."
                ),
                details={"strategy": plan.strategy},
            )
        )

    # Summary aggregations
    is_stale = any(c.conflict_type in STALE_TYPES for c in conflicts)
    requires_manual = plan.requires_manual_approval or any(
        c.conflict_type in (
            ConflictType.IRREVERSIBLE_ACTION.value,
            ConflictType.MANUAL_APPROVAL_REQUIRED.value,
        )
        for c in conflicts
    )

    highest_severity = None
    if conflicts:
        highest_severity = max(
            conflicts,
            key=lambda c: SEVERITY_ORDER.get(c.severity, 0),
        ).severity

    return RecoveryPlanConflictReport(
        plan_id=plan.id,
        execution_id=plan.execution_id,
        workflow_id=plan.workflow_id,
        has_conflicts=len(conflicts) > 0,
        is_stale=is_stale,
        requires_manual_approval=requires_manual,
        conflict_count=len(conflicts),
        highest_severity=highest_severity,
        conflicts=conflicts,
    )
