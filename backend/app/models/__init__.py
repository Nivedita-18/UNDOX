"""
Models package for UNDOX.
Exports all ORM models so they are registered with Base.metadata upon package import.
"""

from backend.app.database import Base
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
from backend.app.models.audit import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
)
from backend.app.models.user import (
    User,
    UserRole,
)
from backend.app.models.workflow import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)

__all__ = [
    "Base",
    "WorkflowInstance",
    "WorkflowStep",
    "WorkflowStatus",
    "StepStatus",
    "WorkflowExecution",
    "ExecutionStep",
    "ExecutionStatus",
    "ExecutionStepStatus",
    "RecoveryPlan",
    "RecoveryPlanAction",
    "RecoveryPlanStatus",
    "RecoveryActionType",
    "RecoveryActionStatus",
    "AuditEvent",
    "AuditEventType",
    "AuditOutcome",
    "User",
    "UserRole",
]
