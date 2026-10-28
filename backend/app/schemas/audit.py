"""
Pydantic schemas for Audit Event request/response data transfer objects.
Uses Pydantic v2 conventions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(str, Enum):
    """Taxonomy of valid audit event types."""
    WORKFLOW_EXECUTION_STARTED = "WORKFLOW_EXECUTION_STARTED"
    WORKFLOW_EXECUTION_COMPLETED = "WORKFLOW_EXECUTION_COMPLETED"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"

    RECOVERY_PLAN_CREATED = "RECOVERY_PLAN_CREATED"
    RECOVERY_PLAN_APPROVED = "RECOVERY_PLAN_APPROVED"
    RECOVERY_PLAN_REJECTED = "RECOVERY_PLAN_REJECTED"

    RECOVERY_EXECUTION_STARTED = "RECOVERY_EXECUTION_STARTED"
    RECOVERY_EXECUTION_COMPLETED = "RECOVERY_EXECUTION_COMPLETED"
    RECOVERY_EXECUTION_FAILED = "RECOVERY_EXECUTION_FAILED"


class AuditOutcome(str, Enum):
    """Taxonomy of valid audit outcome statuses."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STARTED = "STARTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    INFO = "INFO"


class AuditEventResponse(BaseModel):
    """
    Response schema representing an individual audit event log record.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    timestamp: datetime
    execution_id: Optional[UUID] = None
    recovery_plan_id: Optional[UUID] = None
    outcome: str
    actor: Optional[str] = "system"
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuditEventsListResponse(BaseModel):
    """
    Paginated list response containing audit event records.
    """
    items: List[AuditEventResponse]
    total: int
    limit: int
    offset: int
