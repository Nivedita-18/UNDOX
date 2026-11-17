
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


class WorkflowInstance(Base):

    __tablename__ = "workflow_instances"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')",
            name="ck_workflow_instances_status"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Workflow name
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    # Workflow description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Workflow status
    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False
    )

    # Creator of workflow
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Last updated timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow creator
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by]
    )

    # Relationship with workflow steps
    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_order"
    )

    # Relationship with workflow executions
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow"
    )

    def __repr__(self):
        return (
            f"<WorkflowInstance "
            f"id={self.id} "
            f"name={self.name!r} "
            f"status={self.status}>"
        )
