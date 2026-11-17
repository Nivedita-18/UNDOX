
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from ..database import Base


class RecoveryPlan(Base):

    __tablename__ = "recovery_plans"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'GENERATED', 'PENDING', "
            "'APPROVED', 'REJECTED', 'EXECUTING', "
            "'COMPLETED', 'FAILED')",
            name="ck_recovery_plan_status"
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
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    # Recovery plan status
    status: Mapped[str] = mapped_column(
        String(20),
        default="GENERATED",
        nullable=False
    )

    # Plan description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Conflict information
    conflict_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    conflict_report: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # User who created the recovery plan
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # User who reviewed the recovery plan
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Review decision reason
    review_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow execution
    execution: Mapped["WorkflowExecution"] = relationship(
        back_populates="recovery_plans"
    )

    # Relationship with recovery plan creator
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by]
    )

    # Relationship with recovery plan reviewer
    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewed_by]
    )

    # Relationship with recovery actions
    actions: Mapped[list["RecoveryPlanAction"]] = relationship(
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        order_by="RecoveryPlanAction.action_order"
    )

    # Relationship with audit events
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="recovery_plan"
    )

    def __repr__(self):
        return (
            f"<RecoveryPlan "
            f"id={self.id} "
            f"execution_id={self.execution_id} "
            f"status={self.status}>"
        )
