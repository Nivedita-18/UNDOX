
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecoveryDecision(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=2000
    )

    manual_review_acknowledged: bool = False


class RecoveryActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recovery_plan_id: int
    execution_step_id: int | None
    action_order: int
    action_type: str
    description: str | None
    payload: dict[str, Any]
    requires_manual_review: bool
    status: str
    result_payload: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RecoveryPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    status: str
    description: str | None
    conflict_count: int
    conflict_report: dict[str, Any] | None
    created_by: int | None
    reviewed_by: int | None
    review_reason: str | None
    created_at: datetime
    updated_at: datetime
    actions: list[RecoveryActionRead]


class RecoveryExecutionStatusRead(BaseModel):
    recovery_plan_id: int
    execution_id: int
    status: str
    total_actions: int
    completed_actions: int
    failed_actions: int
    pending_actions: int
    actions: list[RecoveryActionRead]
