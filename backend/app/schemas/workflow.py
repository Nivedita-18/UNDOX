
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Input schema for individual workflow step
class WorkflowStepCreate(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=150
    )

    step_order: int = Field(gt=0)

    payload: dict[str, Any] = Field(
        default_factory=dict
    )

    compensation_payload: dict[str, Any] | None = None

    is_reversible: bool = False


# Input schema for creating a workflow
class WorkflowCreate(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=150
    )

    description: str | None = None

    steps: list[WorkflowStepCreate] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_step_order(self):

        orders = [
            step.step_order
            for step in self.steps
        ]

        if len(orders) != len(set(orders)):
            raise ValueError(
                "Duplicate step_order values are not allowed"
            )

        return self


# Response schema for workflow steps
class WorkflowStepRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    name: str
    step_order: int
    payload: dict[str, Any]
    compensation_payload: dict[str, Any] | None
    is_reversible: bool
    created_at: datetime


# Response schema for complete workflow
class WorkflowRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    status: str
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    steps: list[WorkflowStepRead]
