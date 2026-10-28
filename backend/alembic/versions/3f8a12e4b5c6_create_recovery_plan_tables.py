"""create recovery plan tables

Revision ID: 3f8a12e4b5c6
Revises: e561ec94db20
Create Date: 2026-10-27 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3f8a12e4b5c6'
down_revision: Union[str, Sequence[str], None] = 'e561ec94db20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'recovery_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('requires_manual_approval', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recovery_plans_execution_id'), 'recovery_plans', ['execution_id'], unique=False)
    op.create_index(op.f('ix_recovery_plans_workflow_id'), 'recovery_plans', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_recovery_plans_status'), 'recovery_plans', ['status'], unique=False)

    op.create_table(
        'recovery_plan_actions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('action_order', sa.Integer(), nullable=False),
        sa.Column('target_step_order', sa.Integer(), nullable=False),
        sa.Column('target_execution_step_id', sa.UUID(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('target_step_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_reversible', sa.Boolean(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('compensation_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('action_order > 0', name='ck_recovery_plan_action_order_positive'),
        sa.CheckConstraint('target_step_order > 0', name='ck_recovery_plan_target_step_order_positive'),
        sa.ForeignKeyConstraint(['plan_id'], ['recovery_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_execution_step_id'], ['execution_steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'action_order', name='uq_recovery_plan_action_order'),
    )
    op.create_index(op.f('ix_recovery_plan_actions_plan_id'), 'recovery_plan_actions', ['plan_id'], unique=False)
    op.create_index(op.f('ix_recovery_plan_actions_target_execution_step_id'), 'recovery_plan_actions', ['target_execution_step_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_recovery_plan_actions_target_execution_step_id'), table_name='recovery_plan_actions')
    op.drop_index(op.f('ix_recovery_plan_actions_plan_id'), table_name='recovery_plan_actions')
    op.drop_table('recovery_plan_actions')
    op.drop_index(op.f('ix_recovery_plans_status'), table_name='recovery_plans')
    op.drop_index(op.f('ix_recovery_plans_workflow_id'), table_name='recovery_plans')
    op.drop_index(op.f('ix_recovery_plans_execution_id'), table_name='recovery_plans')
    op.drop_table('recovery_plans')
