
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from ..database import Base


class WorkflowStep(Base):

    __tablename__ = "workflow_steps"

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "step_order",
            name="uq_workflow_step_order"
        ),
        CheckConstraint(
            "step_order > 0",
            name="ck_workflow_step_order"
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
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Step name
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    # Step sequence
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Step input configuration
    payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )

    # Compensation data
    compensation_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Reversibility
    is_reversible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with workflow
    workflow: Mapped["WorkflowInstance"] = relationship(
        back_populates="steps"
    )

    # Relationship with execution records
    execution_steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="workflow_step"
    )

    def __repr__(self):
        return (
            f"<WorkflowStep "
            f"id={self.id} "
            f"name={self.name!r} "
            f"step_order={self.step_order}>"
        )
