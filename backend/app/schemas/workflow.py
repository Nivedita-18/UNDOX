"""
Pydantic schemas for Workflow and Step data transfer objects.
Uses Pydantic v2 conventions and strict sequence validation.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StepCreate(BaseModel):
    """
    Schema for a planned step within a new workflow.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Descriptive name of the step (e.g., 'Reserve Inventory')",
    )
    step_order: int = Field(
        ...,
        gt=0,
        description="Positive integer indicating step execution order (must be sequential starting at 1)",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_whitespace(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Step name cannot be empty or whitespace only.")
        return trimmed


class WorkflowCreate(BaseModel):
    """
    Schema for registering a new workflow instance with planned steps.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Descriptive name of the workflow (e.g., 'Order Fulfillment Workflow')",
    )
    steps: List[StepCreate] = Field(
        ...,
        min_length=1,
        description="Non-empty list of planned steps in strict sequential order",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_whitespace(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Workflow name cannot be empty or whitespace only.")
        return trimmed

    @model_validator(mode="after")
    def validate_step_ordering(self) -> "WorkflowCreate":
        """
        Enforce strict step sequence rules:
        1. List of steps cannot be empty.
        2. Sequence must begin at 1.
        3. No duplicate step_order values are allowed.
        4. Step orders must be strictly contiguous with no gaps.
        5. Input must not be silently reordered.
        """
        if not self.steps:
            raise ValueError("Workflow must contain at least one step.")

        orders = [step.step_order for step in self.steps]

        # Check start value
        if orders[0] != 1:
            raise ValueError(
                f"Step ordering must start at 1, but the first step has step_order={orders[0]}."
            )

        # Check for duplicates
        seen = set()
        duplicates = set()
        for o in orders:
            if o in seen:
                duplicates.add(o)
            seen.add(o)

        if duplicates:
            raise ValueError(
                f"Duplicate step_order values detected: {sorted(list(duplicates))}."
            )

        # Check strict contiguous sequence starting at 1 without reordering
        expected_sequence = list(range(1, len(self.steps) + 1))
        if orders != expected_sequence:
            raise ValueError(
                f"Steps must be in strict contiguous sequential order starting at 1 with no gaps. "
                f"Expected order: {expected_sequence}, received order: {orders}."
            )

        return self


class StepResponse(BaseModel):
    """
    Response schema representing an individual workflow step.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    name: str
    step_order: int
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None


class WorkflowResponse(BaseModel):
    """
    Response schema representing a workflow and its ordered steps.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    steps: List[StepResponse] = Field(default_factory=list)


class WorkflowListResponse(BaseModel):
    """
    Response schema for listing workflows with pagination/bounds.
    """
    items: List[WorkflowResponse]
    total: int
