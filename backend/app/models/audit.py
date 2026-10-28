"""
Audit Event SQLAlchemy ORM model for UNDOX.
Defines persistent, append-only activity logs for workflow executions and recovery operations.
Kept strictly separate from mutable execution and recovery models to guarantee historical integrity.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.execution import WorkflowExecution
    from backend.app.models.recovery import RecoveryPlan


class AuditEventType(str, enum.Enum):
    """
    Standardized taxonomy of audit event types across workflow and recovery lifecycles.
    """
    # Workflow Execution Events
    WORKFLOW_EXECUTION_STARTED = "WORKFLOW_EXECUTION_STARTED"
    WORKFLOW_EXECUTION_COMPLETED = "WORKFLOW_EXECUTION_COMPLETED"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"

    # Recovery Plan Events
    RECOVERY_PLAN_CREATED = "RECOVERY_PLAN_CREATED"
    RECOVERY_PLAN_APPROVED = "RECOVERY_PLAN_APPROVED"
    RECOVERY_PLAN_REJECTED = "RECOVERY_PLAN_REJECTED"

    # Recovery Execution Events
    RECOVERY_EXECUTION_STARTED = "RECOVERY_EXECUTION_STARTED"
    RECOVERY_EXECUTION_COMPLETED = "RECOVERY_EXECUTION_COMPLETED"
    RECOVERY_EXECUTION_FAILED = "RECOVERY_EXECUTION_FAILED"


class AuditOutcome(str, enum.Enum):
    """
    Outcome status of an audited event or operation.
    """
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STARTED = "STARTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    INFO = "INFO"


class AuditEvent(Base):
    """
    Represents an immutable, append-only record of an activity or state transition
    within workflow execution or recovery operations.
    """
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recovery_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    actor: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        default="system",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships (navigation only, no cascading deletions)
    execution: Mapped[Optional["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        foreign_keys=[execution_id],
        lazy="select",
    )
    recovery_plan: Mapped[Optional["RecoveryPlan"]] = relationship(
        "RecoveryPlan",
        foreign_keys=[recovery_plan_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent(id={self.id}, event_type='{self.event_type}', "
            f"outcome='{self.outcome}', execution_id={self.execution_id}, "
            f"recovery_plan_id={self.recovery_plan_id})>"
        )
