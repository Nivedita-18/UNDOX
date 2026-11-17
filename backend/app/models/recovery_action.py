
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
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


class RecoveryPlanAction(Base):

    __tablename__ = "recovery_plan_actions"

    __table_args__ = (
        UniqueConstraint(
            "recovery_plan_id",
            "action_order",
            name="uq_recovery_action_order"
        ),

        CheckConstraint(
            "action_order > 0",
            name="ck_recovery_action_order"
        ),

        CheckConstraint(
            "action_type IN ('COMPENSATE', 'RETRY', "
            "'SKIP', 'MANUAL_REVIEW')",
            name="ck_recovery_action_type"
        ),

        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'FAILED', 'SKIPPED')",
            name="ck_recovery_action_status"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Recovery plan Foreign Key
    recovery_plan_id: Mapped[int] = mapped_column(
        ForeignKey(
            "recovery_plans.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Target execution step Foreign Key
    execution_step_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "execution_steps.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # Action sequence
    action_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Action type
    action_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    # Action description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Action configuration
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )

    # Manual approval requirement
    requires_manual_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Action status
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False
    )

    # Result data
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Error information
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

    # Execution timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationship with recovery plan
    recovery_plan: Mapped["RecoveryPlan"] = relationship(
        back_populates="actions"
    )

    # Relationship with original execution step
    execution_step: Mapped["ExecutionStep | None"] = relationship()

    def __repr__(self):
        return (
            f"<RecoveryPlanAction "
            f"id={self.id} "
            f"type={self.action_type} "
            f"status={self.status}>"
        )
