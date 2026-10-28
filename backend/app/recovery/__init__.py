"""
Recovery module package.
"""

from backend.app.recovery.service import (
    ExecutionNotFailedError,
    ExecutionNotFoundError,
    RecoveryError,
    RecoveryPlanDuplicateDecisionError,
    RecoveryPlanExecutionConflictError,
    RecoveryPlanNotApprovedError,
    RecoveryPlanNotFoundError,
    RecoveryPlanStaleError,
    RecoveryPlanUnauthorizedActionError,
    get_recovery_plan_by_id,
    list_recovery_plans_for_execution,
    plan_recovery_for_execution,
    generate_recovery_plan,
)
from backend.app.recovery.conflicts import detect_recovery_conflicts
from backend.app.recovery.executor import (
    approve_recovery_plan,
    execute_recovery_plan,
    get_recovery_execution_status,
    record_plan_decision,
    reject_recovery_plan,
)

__all__ = [
    "RecoveryError",
    "ExecutionNotFoundError",
    "ExecutionNotFailedError",
    "RecoveryPlanNotFoundError",
    "RecoveryPlanNotApprovedError",
    "RecoveryPlanExecutionConflictError",
    "RecoveryPlanDuplicateDecisionError",
    "RecoveryPlanStaleError",
    "RecoveryPlanUnauthorizedActionError",
    "plan_recovery_for_execution",
    "generate_recovery_plan",
    "get_recovery_plan_by_id",
    "list_recovery_plans_for_execution",
    "detect_recovery_conflicts",
    "approve_recovery_plan",
    "reject_recovery_plan",
    "execute_recovery_plan",
    "get_recovery_execution_status",
    "record_plan_decision",
]
