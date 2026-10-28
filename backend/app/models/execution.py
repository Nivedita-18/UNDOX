"""
Execution and ExecutionStep SQLAlchemy ORM models for UNDOX.
Separates runtime execution history from static workflow definitions.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.audit import AuditEvent
    from backend.app.models.recovery import RecoveryPlan
    from backend.app.models.workflow import WorkflowInstance, WorkflowStep


class ExecutionStatus(str, enum.Enum):
    """
    Allowed lifecycle states for a WorkflowExecution run.
    - PENDING: Queued or initialized, awaiting execution.
    - RUNNING: Steps are actively being executed.
    - COMPLETED: All planned steps executed successfully.
    - FAILED: Halted due to an injected or unexpected step failure.
    - CANCELLED: Execution was explicitly aborted before completion.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionStepStatus(str, enum.Enum):
    """
    Allowed lifecycle states for an ExecutionStep.
    - PENDING: Not yet reached; waiting for preceding steps to finish.
    - RUNNING: Actively simulating step execution.
    - COMPLETED: Step finished successfully.
    - FAILED: Step execution halted with an error.
    - SKIPPED: Step bypassed (e.g. following a prior step failure).
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowExecution(Base):
    """
    Represents an individual execution attempt for a WorkflowInstance.
    Preserves historical execution records across repeated runs.
    """
    __tablename__ = "workflow_executions"

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "attempt_number",
            name="uq_workflow_execution_attempt",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_workflow_execution_attempt_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ExecutionStatus.PENDING.value,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SIMULATED",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    failure_simulation_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to parent workflow definition
    workflow: Mapped["WorkflowInstance"] = relationship(
        back_populates="executions",
    )

    # Ordered steps for this execution attempt
    execution_steps: Mapped[List["ExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.step_order",
    )

    # Generated recovery plans for this execution
    recovery_plans: Mapped[List["RecoveryPlan"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="RecoveryPlan.created_at.desc()",
    )

    # Immutable audit events related to this execution
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="execution",
        order_by="AuditEvent.timestamp.asc()",
        foreign_keys="AuditEvent.execution_id",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowExecution(id={self.id}, workflow_id={self.workflow_id}, "
            f"attempt={self.attempt_number}, status='{self.status}')>"
        )


class ExecutionStep(Base):
    """
    Represents the execution state of an individual step during a specific WorkflowExecution run.
    """
    __tablename__ = "execution_steps"

    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "step_order",
            name="uq_execution_step_order",
        ),
        CheckConstraint(
            "step_order > 0",
            name="ck_execution_step_order_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ExecutionStepStatus.PENDING.value,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    step_output: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to parent execution
    execution: Mapped["WorkflowExecution"] = relationship(
        back_populates="execution_steps",
    )

    # Reference to original workflow step definition (RESTRICT on delete, no ORM cascade)
    workflow_step: Mapped["WorkflowStep"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ExecutionStep(id={self.id}, execution_id={self.execution_id}, "
            f"order={self.step_order}, name='{self.name}', status='{self.status}')>"
        )
