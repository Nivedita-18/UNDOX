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


def test_models_registered_in_metadata():
    """
    Ensure all four core models are registered in Base.metadata.
    """
    table_names = Base.metadata.tables.keys()
    assert "workflow_instances" in table_names
    assert "workflow_steps" in table_names
    assert "workflow_executions" in table_names
    assert "execution_steps" in table_names


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
