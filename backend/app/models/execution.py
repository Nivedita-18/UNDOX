
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from ..database import Base


class WorkflowExecution(Base):

    __tablename__ = "workflow_executions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'FAILED', 'CANCELLED')",
            name="ck_workflow_execution_status"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Workflow Foreign Key
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey(
            "workflow_instances.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    # User who triggered execution
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False
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

    # Failure information
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow
    workflow: Mapped["WorkflowInstance"] = relationship(
        back_populates="executions"
    )

    # Relationship with triggering user
    triggered_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[triggered_by]
    )

    # Relationship with execution steps
    steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.step_order"
    )

    # Relationship with recovery plans
    recovery_plans: Mapped[list["RecoveryPlan"]] = relationship(
        back_populates="execution"
    )

    # Relationship with audit events
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="execution"
    )

    def __repr__(self):
        return (
            f"<WorkflowExecution "
            f"id={self.id} "
            f"workflow_id={self.workflow_id} "
            f"status={self.status}>"
        )
