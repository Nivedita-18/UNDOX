
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from ..database import Base


class User(Base):

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'OPERATOR', 'VIEWER')",
            name="ck_users_role"
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # User email
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    # Securely hashed password
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # User role
    role: Mapped[str] = mapped_column(
        String(20),
        default="VIEWER",
        nullable=False
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Account creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship with audit events
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="actor"
    )

    def __repr__(self):
        return (
            f"<User id={self.id} "
            f"email={self.email!r} "
            f"role={self.role}>"
        )
