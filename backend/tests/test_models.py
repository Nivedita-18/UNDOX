"""
Tests for UNDOX SQLAlchemy models:
- WorkflowInstance and WorkflowStep (Blueprint definitions)
- WorkflowExecution and ExecutionStep (Runtime attempt records)
Validates table metadata, column definitions, constraints, and relationships.
"""

import uuid
from backend.app.database import Base
from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    WorkflowExecution,
)
from backend.app.models.workflow import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from backend.app.models.recovery import (
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryPlan,
    RecoveryPlanAction,
    RecoveryPlanStatus,
)
from backend.app.models.audit import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
)
from backend.app.models.user import (
    User,
    UserRole,
)


def test_models_registered_in_metadata():
    """
    Ensure all core models (workflow, execution, recovery, audit, user) are registered in Base.metadata.
    """
    table_names = Base.metadata.tables.keys()
    assert "workflow_instances" in table_names
    assert "workflow_steps" in table_names
    assert "workflow_executions" in table_names
    assert "execution_steps" in table_names
    assert "recovery_plans" in table_names
    assert "recovery_plan_actions" in table_names
    assert "audit_events" in table_names
    assert "users" in table_names


def test_workflow_instance_table_structure():
    """
    Validate the columns, constraints, and nullability of workflow_instances.
    """
    table = Base.metadata.tables["workflow_instances"]

    # Primary key
    assert table.c.id.primary_key is True

    # Required fields
    assert table.c.name.nullable is False
    assert table.c.status.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False


def test_workflow_step_table_structure():
    """
    Validate the columns, foreign keys, and constraints of workflow_steps.
    """
    table = Base.metadata.tables["workflow_steps"]

    # Primary key
    assert table.c.id.primary_key is True

    # Foreign key to workflow_instances
    fk_targets = [fk.target_fullname for fk in table.foreign_keys]
    assert "workflow_instances.id" in fk_targets

    # Required fields
    assert table.c.workflow_id.nullable is False
    assert table.c.name.nullable is False
    assert table.c.step_order.nullable is False
    assert table.c.status.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False

    # Optional fields
    assert table.c.error_message.nullable is True

    # Unique constraint on (workflow_id, step_order)
    uq_constraints = [
        c.name for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1
    ]
    assert "uq_workflow_step_order" in uq_constraints


def test_workflow_execution_table_structure():
    """
    Validate columns, constraints, foreign keys, and indexes of workflow_executions.
    """
    table = Base.metadata.tables["workflow_executions"]

    assert table.c.id.primary_key is True

    # Foreign key to workflow_instances with CASCADE
    fks = list(table.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "workflow_instances.id"
    assert fks[0].ondelete == "CASCADE"

    # Required fields
    assert table.c.workflow_id.nullable is False
    assert table.c.attempt_number.nullable is False
    assert table.c.status.nullable is False
    assert table.c.trigger_type.nullable is False
    assert table.c.created_at.nullable is False

    # Nullable execution lifecycle fields
    assert table.c.started_at.nullable is True
    assert table.c.completed_at.nullable is True
    assert table.c.failure_reason.nullable is True
    assert table.c.failure_simulation_config.nullable is True

    # Constraints
    constraint_names = {c.name for c in table.constraints}
    assert "uq_workflow_execution_attempt" in constraint_names
    assert "ck_workflow_execution_attempt_positive" in constraint_names


def test_execution_step_table_structure():
    """
    Validate columns, constraints, foreign keys, and indexes of execution_steps.
    """
    table = Base.metadata.tables["execution_steps"]

    assert table.c.id.primary_key is True

    # Verify foreign keys: execution_id (CASCADE), workflow_step_id (RESTRICT)
    fk_map = {fk.target_fullname: fk.ondelete for fk in table.foreign_keys}
    assert fk_map["workflow_executions.id"] == "CASCADE"
    assert fk_map["workflow_steps.id"] == "RESTRICT"

    # Required fields
    assert table.c.execution_id.nullable is False
    assert table.c.workflow_step_id.nullable is False
    assert table.c.step_order.nullable is False
    assert table.c.name.nullable is False
    assert table.c.status.nullable is False
    assert table.c.created_at.nullable is False

    # Nullable step runtime fields
    assert table.c.started_at.nullable is True
    assert table.c.completed_at.nullable is True
    assert table.c.error_message.nullable is True
    assert table.c.step_output.nullable is True

    # Constraints
    constraint_names = {c.name for c in table.constraints}
    assert "uq_execution_step_order" in constraint_names
    assert "ck_execution_step_order_positive" in constraint_names


def test_enum_status_values():
    """
    Verify all required status enum values across definition and execution models.
    """
    # WorkflowStatus (Blueprint)
    assert WorkflowStatus.PENDING.value == "PENDING"
    assert WorkflowStatus.RUNNING.value == "RUNNING"
    assert WorkflowStatus.COMPLETED.value == "COMPLETED"
    assert WorkflowStatus.FAILED.value == "FAILED"
    assert WorkflowStatus.CANCELLED.value == "CANCELLED"

    # StepStatus (Blueprint)
    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus.RUNNING.value == "RUNNING"
    assert StepStatus.COMPLETED.value == "COMPLETED"
    assert StepStatus.FAILED.value == "FAILED"
    assert StepStatus.COMPENSATED.value == "COMPENSATED"
    assert StepStatus.SKIPPED.value == "SKIPPED"

    # ExecutionStatus (Runtime run)
    assert ExecutionStatus.PENDING.value == "PENDING"
    assert ExecutionStatus.RUNNING.value == "RUNNING"
    assert ExecutionStatus.COMPLETED.value == "COMPLETED"
    assert ExecutionStatus.FAILED.value == "FAILED"
    assert ExecutionStatus.CANCELLED.value == "CANCELLED"

    # ExecutionStepStatus (Runtime step)
    assert ExecutionStepStatus.PENDING.value == "PENDING"
    assert ExecutionStepStatus.RUNNING.value == "RUNNING"
    assert ExecutionStepStatus.COMPLETED.value == "COMPLETED"
    assert ExecutionStepStatus.FAILED.value == "FAILED"
    assert ExecutionStepStatus.SKIPPED.value == "SKIPPED"

    # RecoveryPlanStatus
    assert RecoveryPlanStatus.DRAFT.value == "DRAFT"
    assert RecoveryPlanStatus.GENERATED.value == "GENERATED"
    assert RecoveryPlanStatus.PENDING.value == "PENDING"
    assert RecoveryPlanStatus.APPROVED.value == "APPROVED"
    assert RecoveryPlanStatus.REJECTED.value == "REJECTED"
    assert RecoveryPlanStatus.EXECUTING.value == "EXECUTING"
    assert RecoveryPlanStatus.COMPLETED.value == "COMPLETED"
    assert RecoveryPlanStatus.FAILED.value == "FAILED"

    # RecoveryActionStatus
    assert RecoveryActionStatus.PROPOSED.value == "PROPOSED"
    assert RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value == "REQUIRES_MANUAL_REVIEW"
    assert RecoveryActionStatus.EXECUTING.value == "EXECUTING"
    assert RecoveryActionStatus.COMPLETED.value == "COMPLETED"
    assert RecoveryActionStatus.FAILED.value == "FAILED"
    assert RecoveryActionStatus.SKIPPED.value == "SKIPPED"

    # AuditEventType
    assert AuditEventType.WORKFLOW_EXECUTION_STARTED.value == "WORKFLOW_EXECUTION_STARTED"
    assert AuditEventType.WORKFLOW_EXECUTION_COMPLETED.value == "WORKFLOW_EXECUTION_COMPLETED"
    assert AuditEventType.WORKFLOW_EXECUTION_FAILED.value == "WORKFLOW_EXECUTION_FAILED"
    assert AuditEventType.RECOVERY_PLAN_CREATED.value == "RECOVERY_PLAN_CREATED"
    assert AuditEventType.RECOVERY_PLAN_APPROVED.value == "RECOVERY_PLAN_APPROVED"
    assert AuditEventType.RECOVERY_PLAN_REJECTED.value == "RECOVERY_PLAN_REJECTED"
    assert AuditEventType.RECOVERY_EXECUTION_STARTED.value == "RECOVERY_EXECUTION_STARTED"
    assert AuditEventType.RECOVERY_EXECUTION_COMPLETED.value == "RECOVERY_EXECUTION_COMPLETED"
    assert AuditEventType.RECOVERY_EXECUTION_FAILED.value == "RECOVERY_EXECUTION_FAILED"

    # AuditOutcome
    assert AuditOutcome.SUCCESS.value == "SUCCESS"
    assert AuditOutcome.FAILED.value == "FAILED"
    assert AuditOutcome.STARTED.value == "STARTED"
    assert AuditOutcome.APPROVED.value == "APPROVED"
    assert AuditOutcome.REJECTED.value == "REJECTED"
    assert AuditOutcome.WARNING.value == "WARNING"
    assert AuditOutcome.INFO.value == "INFO"

    # UserRole
    assert UserRole.ADMIN.value == "ADMIN"
    assert UserRole.OPERATOR.value == "OPERATOR"
    assert UserRole.VIEWER.value == "VIEWER"


def test_in_memory_model_relationship_navigation():
    """
    Verify in-memory model instantiation and bidirectional relationship navigation
    across definition models and runtime execution models.
    """
    wf_id = uuid.uuid4()
    workflow = WorkflowInstance(
        id=wf_id,
        name="Order Processing",
        status=WorkflowStatus.PENDING.value,
    )

    wf_step = WorkflowStep(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        name="Validate Order",
        step_order=1,
        status=StepStatus.PENDING.value,
    )
    workflow.steps.append(wf_step)

    # Create Execution Attempt 1
    exec_id = uuid.uuid4()
    execution = WorkflowExecution(
        id=exec_id,
        workflow_id=wf_id,
        attempt_number=1,
        status=ExecutionStatus.RUNNING.value,
    )
    workflow.executions.append(execution)

    # Create ExecutionStep 1 for Attempt 1
    exec_step = ExecutionStep(
        id=uuid.uuid4(),
        execution_id=exec_id,
        workflow_step_id=wf_step.id,
        step_order=1,
        name=wf_step.name,
        status=ExecutionStepStatus.RUNNING.value,
    )
    execution.execution_steps.append(exec_step)
    exec_step.workflow_step = wf_step

    # Assert navigation
    assert len(workflow.executions) == 1
    assert workflow.executions[0].attempt_number == 1
    assert len(execution.execution_steps) == 1
    assert execution.execution_steps[0].name == "Validate Order"
    assert exec_step.execution is execution
    assert exec_step.workflow_step is wf_step
    assert execution.workflow is workflow


def test_recovery_plan_table_structure():
    """
    Validate the columns, foreign keys, and indexes of recovery_plans table.
    """
    table = Base.metadata.tables["recovery_plans"]

    # Primary key
    assert table.c.id.primary_key is True

    # Required fields
    assert table.c.execution_id.nullable is False
    assert table.c.workflow_id.nullable is False
    assert table.c.status.nullable is False
    assert table.c.strategy.nullable is False
    assert table.c.summary.nullable is False
    assert table.c.requires_manual_approval.nullable is False

    # Foreign keys
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "workflow_executions.id" in fk_targets
    assert "workflow_instances.id" in fk_targets


def test_recovery_plan_action_table_structure():
    """
    Validate the columns, constraints, and foreign keys of recovery_plan_actions table.
    """
    table = Base.metadata.tables["recovery_plan_actions"]

    # Primary key
    assert table.c.id.primary_key is True

    # Required fields
    assert table.c.plan_id.nullable is False
    assert table.c.action_order.nullable is False
    assert table.c.target_step_order.nullable is False
    assert table.c.action_type.nullable is False
    assert table.c.target_step_name.nullable is False
    assert table.c.status.nullable is False
    assert table.c.is_reversible.nullable is False
    assert table.c.explanation.nullable is False

    # Foreign keys
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "recovery_plans.id" in fk_targets
    assert "execution_steps.id" in fk_targets

    # Check constraints and unique constraints
    ck_names = [c.name for c in table.constraints if hasattr(c, "name") and c.name]
    assert "ck_recovery_plan_action_order_positive" in ck_names
    assert "ck_recovery_plan_target_step_order_positive" in ck_names
    assert "uq_recovery_plan_action_order" in ck_names


def test_audit_event_table_structure():
    """
    Validate the columns, indexes, and foreign keys of audit_events table.
    """
    table = Base.metadata.tables["audit_events"]

    # Primary key
    assert table.c.id.primary_key is True

    # Required fields
    assert table.c.event_type.nullable is False
    assert table.c.timestamp.nullable is False
    assert table.c.outcome.nullable is False
    assert table.c.message.nullable is False
    assert table.c.created_at.nullable is False

    # Optional fields
    assert table.c.execution_id.nullable is True
    assert table.c.recovery_plan_id.nullable is True
    assert table.c.actor.nullable is True
    assert table.c.details.nullable is True

    # Foreign keys
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "workflow_executions.id" in fk_targets
    assert "recovery_plans.id" in fk_targets


def test_user_table_structure():
    """
    Validate the columns and constraints of users table.
    """
    table = Base.metadata.tables["users"]

    # Primary key
    assert table.c.id.primary_key is True

    # Required fields
    assert table.c.username.nullable is False
    assert table.c.email.nullable is False
    assert table.c.hashed_password.nullable is False
    assert table.c.role.nullable is False
    assert table.c.is_active.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False



