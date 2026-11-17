
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from ..database import Base


class ExecutionStep(Base):

    __tablename__ = "execution_steps"

    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "step_order",
            name="uq_execution_step_order"
        ),
        CheckConstraint(
            "step_order > 0",
            name="ck_execution_step_order"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'FAILED', 'SKIPPED')",
            name="ck_execution_step_status"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Execution Foreign Key
    execution_id: Mapped[int] = mapped_column(
        ForeignKey(
            "workflow_executions.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Original workflow step reference
    workflow_step_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "workflow_steps.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # Step snapshot
    step_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False
    )

    # Input and output data
    input_payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )

    output_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Error information
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Execution timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow execution
    execution: Mapped["WorkflowExecution"] = relationship(
        back_populates="steps"
    )

    # Relationship with original workflow step
    workflow_step: Mapped["WorkflowStep | None"] = relationship(
        back_populates="execution_steps"
    )

    def __repr__(self):
        return (
            f"<ExecutionStep "
            f"id={self.id} "
            f"step_name={self.step_name!r} "
            f"status={self.status}>"
        )
