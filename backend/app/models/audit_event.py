
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
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


class AuditEvent(Base):

    __tablename__ = "audit_events"

    __table_args__ = (
        Index(
            "ix_audit_events_event_type_created_at",
            "event_type",
            "created_at"
        ),
        Index(
            "ix_audit_events_outcome_created_at",
            "outcome",
            "created_at"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Event information
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    outcome: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # User who performed the action
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Related workflow execution
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "workflow_executions.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # Related recovery plan
    recovery_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "recovery_plans.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # Additional event information
    event_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Event timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow execution
    execution: Mapped["WorkflowExecution | None"] = relationship(
        back_populates="audit_events"
    )

    # Relationship with recovery plan
    recovery_plan: Mapped["RecoveryPlan | None"] = relationship(
        back_populates="audit_events"
    )

    # Relationship with user
    actor: Mapped["User | None"] = relationship(
        back_populates="audit_events"
    )

    def __repr__(self):
        return (
            f"<AuditEvent id={self.id} "
            f"type={self.event_type!r} "
            f"outcome={self.outcome!r}>"
        )
