
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)


class AuditEventRead(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int = Field(gt=0)

    event_type: str = Field(
        min_length=1,
        max_length=100
    )

    outcome: str | None = Field(
        default=None,
        max_length=50
    )

    message: str | None = None

    actor_id: int | None = None

    execution_id: int | None = None

    recovery_plan_id: int | None = None

    event_data: dict[str, Any] | None = None

    created_at: datetime
