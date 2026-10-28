"""create audit events table

Revision ID: 4a8c91d2e3f4
Revises: 3f8a12e4b5c6
Create Date: 2026-10-28 10:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4a8c91d2e3f4'
down_revision: Union[str, Sequence[str], None] = '3f8a12e4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('recovery_plan_id', sa.UUID(), nullable=True),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('actor', sa.String(length=128), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recovery_plan_id'], ['recovery_plans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_events_timestamp'), 'audit_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_events_execution_id'), 'audit_events', ['execution_id'], unique=False)
    op.create_index(op.f('ix_audit_events_recovery_plan_id'), 'audit_events', ['recovery_plan_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_audit_events_recovery_plan_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_execution_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_timestamp'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_event_type'), table_name='audit_events')
    op.drop_table('audit_events')
