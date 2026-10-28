"""
Pydantic schemas for Recovery Plan request/response data transfer objects.
Uses Pydantic v2 conventions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecoveryPlanActionResponse(BaseModel):
    """
    Response schema representing an individual proposed recovery action.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    action_order: int
    target_step_order: int
    target_execution_step_id: Optional[UUID] = None
    action_type: str
    target_step_name: str
    status: str
    is_reversible: bool
    explanation: str
    compensation_details: Optional[Dict[str, Any]] = None
    created_at: datetime


class RecoveryPlanResponse(BaseModel):
    """
    Response schema representing a complete recovery plan with all proposed actions.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execution_id: UUID
    workflow_id: UUID
    strategy: str
    status: str
    summary: str
    requires_manual_approval: bool
    created_at: datetime
    updated_at: datetime
    decision_reason: Optional[str] = None
    decision_operator: Optional[str] = None
    decided_at: Optional[datetime] = None
    actions: List[RecoveryPlanActionResponse] = Field(default_factory=list)


class RecoveryPlanRequest(BaseModel):
    """
    Request body for generating a failure recovery plan for an execution.
    """
    strategy: Optional[str] = Field(
        default=None,
        description="Explicit recovery strategy override (e.g. SAGA_COMPENSATE, RETRY_FAILED_ONLY, MANUAL_REVIEW)",
    )
    strategy_preference: Optional[str] = Field(
        default="AUTO",
        description="Preferred recovery strategy: AUTO, SAGA_COMPENSATE, or RETRY",
    )
    unsupported_steps: Optional[List[int]] = Field(
        default_factory=list,
        description="List of step_orders that cannot be automatically reversed and require manual review",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional operator notes or instructions for the recovery planner",
    )

    @field_validator("unsupported_steps")
    @classmethod
    def validate_unsupported_steps(cls, v: Optional[List[int]]) -> List[int]:
        if v is None:
            return []
        for step_order in v:
            if step_order <= 0:
                raise ValueError("Step order numbers in unsupported_steps must be greater than 0")
        return v


class ConflictSeverity(str, Enum):
    """
    Severity rating for detected recovery plan conflicts.
    - CRITICAL: Plan is invalid/stale, execution succeeded/running, or concurrent execution exists.
    - HIGH: Direct intra-plan action contradiction, duplicate target step, or ordering violation.
    - MEDIUM: Irreversible side effect or manual review requirement.
    - LOW: Non-blocking warning or informational notice.
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConflictType(str, Enum):
    """
    Classification of recovery conflicts detected by the Conflict Detection Engine.
    """
    STALE_PLAN_EXECUTION_STATUS_CHANGED = "STALE_PLAN_EXECUTION_STATUS_CHANGED"
    STALE_PLAN_SUPERSEDED_EXECUTION = "STALE_PLAN_SUPERSEDED_EXECUTION"
    STALE_PLAN_WORKFLOW_STATE_INCOMPATIBLE = "STALE_PLAN_WORKFLOW_STATE_INCOMPATIBLE"
    STALE_STEP_STATE_MISMATCH = "STALE_STEP_STATE_MISMATCH"
    SUPERSEDED_BY_NEWER_PLAN = "SUPERSEDED_BY_NEWER_PLAN"
    DUPLICATE_ACTION = "DUPLICATE_ACTION"
    CONTRADICTORY_ACTIONS = "CONTRADICTORY_ACTIONS"
    ORDERING_CONFLICT = "ORDERING_CONFLICT"
    ACTIVE_PLAN_CONCURRENCY = "ACTIVE_PLAN_CONCURRENCY"
    IRREVERSIBLE_ACTION = "IRREVERSIBLE_ACTION"
    MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"


class ConflictDetail(BaseModel):
    """
    Detailed description of an individual detected conflict within a recovery plan.
    """
    model_config = ConfigDict(from_attributes=True)

    conflict_type: str
    severity: str
    message: str
    step_order: Optional[int] = None
    step_name: Optional[str] = None
    action_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None


class RecoveryPlanConflictReport(BaseModel):
    """
    Structured conflict and staleness inspection report for a RecoveryPlan.
    """
    model_config = ConfigDict(from_attributes=True)

    plan_id: UUID
    execution_id: UUID
    workflow_id: UUID
    has_conflicts: bool
    is_stale: bool
    requires_manual_approval: bool
    conflict_count: int
    highest_severity: Optional[str] = None
    conflicts: List[ConflictDetail] = Field(default_factory=list)


class RecoveryPlanApprovalRequest(BaseModel):
    """
    Request payload for operator review and approval of a recovery plan.
    """
    authorize_manual_review: bool = Field(
        default=False,
        description="Explicit authorization for irreversible actions or actions requiring manual review",
    )
    operator: Optional[str] = Field(
        default="operator",
        description="Identifier of the operator or service approving the plan",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Operator justification or audit notes for approval",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional operator review notes or instructions",
    )


class RecoveryPlanRejectionRequest(BaseModel):
    """
    Request payload for operator rejection of a recovery plan.
    """
    reason: Optional[str] = Field(
        default="Rejected by operator",
        max_length=1000,
        description="Operator explanation or reason for rejecting the recovery plan",
    )
    operator: Optional[str] = Field(
        default="operator",
        description="Identifier of the operator or service rejecting the plan",
    )


class RecoveryExecutionRequest(BaseModel):
    """
    Request payload for controlled execution of an approved recovery plan.
    """
    simulate_action_failure_at_order: Optional[int] = Field(
        default=None,
        description="Simulate action failure at a specific action_order for resiliency testing",
    )
    simulated_error_message: Optional[str] = Field(
        default="Simulated recovery action execution error",
        description="Custom error message when simulating an action failure",
    )


class RecoveryExecutionStatusResponse(BaseModel):
    """
    Detailed runtime progress and execution status for a recovery plan.
    """
    model_config = ConfigDict(from_attributes=True)

    plan_id: UUID
    execution_id: UUID
    workflow_id: UUID
    status: str
    strategy: str
    requires_manual_approval: bool
    total_actions: int
    completed_actions: int
    failed_actions: int
    pending_actions: int
    created_at: datetime
    updated_at: datetime
    actions: List[RecoveryPlanActionResponse] = Field(default_factory=list)

