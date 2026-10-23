"""
Workflow and Step SQLAlchemy ORM models for UNDOX.
Uses SQLAlchemy 2.0 style declarative mappings and UUID primary keys.
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.execution import WorkflowExecution


class WorkflowStatus(str, enum.Enum):
    """
    Allowed lifecycle states for a WorkflowInstance.
    - PENDING: Newly created workflow, waiting to execute.
    - RUNNING: Workflow is actively executing steps.
    - COMPLETED: All workflow steps executed successfully.
    - FAILED: At least one step failed; workflow requires evaluation/recovery.
    - RECOVERING: Compensating actions are currently being executed.
    - RECOVERED: Recovery completed successfully; state has been reconciled.
    - CANCELLED: Workflow execution was halted before completion.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    CANCELLED = "CANCELLED"


class StepStatus(str, enum.Enum):
    """
    Allowed lifecycle states for a WorkflowStep.
    - PENDING: Step is queued and waiting for preceding steps to complete.
    - RUNNING: Step is actively executing its action.
    - COMPLETED: Step finished successfully.
    - FAILED: Step execution failed with an error.
    - COMPENSATED: Step was undone or compensated during failure recovery.
    - SKIPPED: Step was bypassed.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"
    SKIPPED = "SKIPPED"


class WorkflowInstance(Base):
    """
    Represents an individual execution instance of a multi-step workflow.
    """
    __tablename__ = "workflow_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WorkflowStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to ordered steps
    steps: Mapped[List["WorkflowStep"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_order",
    )

    # Relationship to executions
    executions: Mapped[List["WorkflowExecution"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowExecution.attempt_number",
    )

    def __repr__(self) -> str:
        return f"<WorkflowInstance(id={self.id}, name='{self.name}', status='{self.status}')>"


class WorkflowStep(Base):
    """
    Represents a single step in a workflow instance.
    Steps have a strict sequence order within each workflow.
    """
    __tablename__ = "workflow_steps"

    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_workflow_step_order"),
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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=StepStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Back-reference to the parent workflow
    workflow: Mapped["WorkflowInstance"] = relationship(
        back_populates="steps",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowStep(id={self.id}, workflow_id={self.workflow_id}, "
            f"order={self.step_order}, name='{self.name}', status='{self.status}')>"
        )
