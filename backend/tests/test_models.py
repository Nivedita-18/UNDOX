"""
Tests for UNDOX SQLAlchemy models: WorkflowInstance and WorkflowStep.
Validates table metadata, column definitions, constraints, and relationships.
"""

import uuid
from sqlalchemy import inspect
from backend.app.database import Base
from backend.app.models.workflow import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)


def test_models_registered_in_metadata():
    """
    Ensure WorkflowInstance and WorkflowStep are registered in Base.metadata.
    """
    table_names = Base.metadata.tables.keys()
    assert "workflow_instances" in table_names
    assert "workflow_steps" in table_names


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


def test_enum_status_values():
    """
    Verify all required status enum values are present.
    """
    # WorkflowStatus checks
    assert WorkflowStatus.PENDING.value == "PENDING"
    assert WorkflowStatus.RUNNING.value == "RUNNING"
    assert WorkflowStatus.COMPLETED.value == "COMPLETED"
    assert WorkflowStatus.FAILED.value == "FAILED"
    assert WorkflowStatus.RECOVERING.value == "RECOVERING"
    assert WorkflowStatus.RECOVERED.value == "RECOVERED"
    assert WorkflowStatus.CANCELLED.value == "CANCELLED"

    # StepStatus checks
    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus.RUNNING.value == "RUNNING"
    assert StepStatus.COMPLETED.value == "COMPLETED"
    assert StepStatus.FAILED.value == "FAILED"
    assert StepStatus.COMPENSATED.value == "COMPENSATED"
    assert StepStatus.SKIPPED.value == "SKIPPED"


def test_in_memory_model_relationship():
    """
    Verify in-memory model instantiation and bidirectional relationship navigation.
    """
    wf_id = uuid.uuid4()
    workflow = WorkflowInstance(
        id=wf_id,
        name="Checkout Workflow",
        status=WorkflowStatus.PENDING.value,
    )

    step1 = WorkflowStep(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        name="Validate Cart",
        step_order=1,
        status=StepStatus.PENDING.value,
    )
    step2 = WorkflowStep(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        name="Process Payment",
        step_order=2,
        status=StepStatus.PENDING.value,
    )

    # Establish relationship
    workflow.steps.append(step1)
    workflow.steps.append(step2)

    assert len(workflow.steps) == 2
    assert workflow.steps[0].name == "Validate Cart"
    assert workflow.steps[1].name == "Process Payment"
    assert step1.workflow is workflow
    assert step2.workflow is workflow
