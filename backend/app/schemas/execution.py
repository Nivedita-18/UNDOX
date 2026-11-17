
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator
)


class ExecutionRequest(BaseModel):

    # Enable controlled failure simulation
    simulate_failure: bool = False

    # Step number where failure should occur
    failure_step_order: int | None = Field(
        default=None,
        gt=0
    )

    # Custom failure message
    failure_message: str = Field(
        default="Simulated workflow step failure",
        min_length=1,
        max_length=1000
    )

    @model_validator(mode="after")
    def validate_failure_configuration(self):

        if self.simulate_failure and self.failure_step_order is None:
            raise ValueError(
                "failure_step_order is required when "
                "simulate_failure is true"
            )

        if not self.simulate_failure and self.failure_step_order is not None:
            raise ValueError(
                "failure_step_order requires simulate_failure=true"
            )

        return self


class ExecutionStepRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    workflow_step_id: int | None

    step_name: str
    step_order: int
    status: str

    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None

    error_message: str | None

    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ExecutionRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    triggered_by: int | None

    status: str

    started_at: datetime | None
    finished_at: datetime | None

    error_message: str | None
    created_at: datetime

    steps: list[ExecutionStepRead]
