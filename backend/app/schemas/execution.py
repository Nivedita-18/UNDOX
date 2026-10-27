"""
Pydantic schemas for workflow execution request/response data transfer objects.
Uses Pydantic v2 conventions. Domain-neutral — no e-commerce or industry-specific logic.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class FailureSimulationConfig(BaseModel):
    """
    Configuration for injecting a controlled failure during execution.
    Used to test recovery mechanisms without real external service failures.

    - fail_at_step_order: The step_order at which execution should be
      forced to fail. Must be a positive integer referencing an existing
      workflow step's step_order.
    - error_message: An optional custom error message for the simulated
      failure (defaults to a generic message if omitted).
    """
    fail_at_step_order: int = Field(
        ...,
        gt=0,
        description="step_order of the step that should fail during execution",
    )
    error_message: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Custom error message for the simulated failure",
    )


class ExecutionRequest(BaseModel):
    """
    Request body for triggering a workflow execution.

    - failure_simulation: Optional failure injection configuration.
      When omitted, execution proceeds without injected failures.
    """
    failure_simulation: Optional[FailureSimulationConfig] = Field(
        default=None,
        description="Optional configuration to inject a controlled failure at a specific step",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExecutionStepResponse(BaseModel):
    """
    Response schema representing the execution state of a single step
    within a WorkflowExecution run.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execution_id: UUID
    workflow_step_id: UUID
    step_order: int
    name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    step_output: Optional[Dict[str, Any]] = None
    created_at: datetime


class ExecutionResponse(BaseModel):
    """
    Response schema representing a complete WorkflowExecution attempt,
    including all execution step states.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    attempt_number: int
    status: str
    trigger_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    failure_simulation_config: Optional[Dict[str, Any]] = None
    created_at: datetime
    execution_steps: List[ExecutionStepResponse] = Field(default_factory=list)


class ExecutionSummaryResponse(BaseModel):
    """
    Lightweight summary of an execution attempt (without step details).
    Useful for listing multiple executions without N+1 step loading.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    attempt_number: int
    status: str
    trigger_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
