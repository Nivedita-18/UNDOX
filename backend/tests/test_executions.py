"""
Tests for the Workflow Execution Service, Execution Schemas, and Execution REST API.

Covers:
- Schema validation for ExecutionRequest and FailureSimulationConfig.
- Execution Service against database:
  - Successful full execution (all steps COMPLETED).
  - Controlled failure injection (targeted step FAILED, later steps remain PENDING).
  - Repeated execution attempts (attempt_number increments correctly).
  - Invalid failure injection (nonexistent step_order rejected before any record is created).
  - Active-execution conflict detection (PENDING/RUNNING blocks new execution).
  - Execution retrieval by ID.
  - Verification that workflow definition steps are not mutated during execution.
- Execution REST API:
  - POST /workflows/{id}/execute (success, failure simulation, validation errors, 404, 400).
  - GET /executions/{id} (success, 404 for nonexistent, 422 for invalid UUID).
- Real concurrent PostgreSQL transaction safety (skipped on SQLite).

Uses hermetic test database setup and cleanup conventions.
"""

import os
import threading
import uuid
from typing import Generator, List

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    WorkflowExecution,
)
from backend.app.models.workflow import (
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
    StepStatus,
)
from backend.app.schemas.execution import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStepResponse,
    FailureSimulationConfig,
)
from backend.app.executions.service import (
    ActiveExecutionConflictError,
    InvalidFailureConfigError,
    WorkflowNotFoundError,
    execute_workflow,
    get_execution_by_id,
)

# ---------------------------------------------------------------------------
# Test database engine and session factory
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

Base.metadata.create_all(bind=test_engine)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """
    Ensure the FastAPI application uses the test database for all endpoints
    during execution test runs.
    """
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


# ---------------------------------------------------------------------------
# FIXTURE: Create a test workflow and clean up after each test
# ---------------------------------------------------------------------------
@pytest.fixture
def test_workflow() -> Generator:
    """
    Creates a 3-step workflow in the test database for use in execution tests.
    Tracks created workflow IDs and cleans up only those rows in teardown.
    Also cleans up any execution records created during the test.
    """
    db = TestingSessionLocal()
    created_workflow_ids: List[uuid.UUID] = []
    created_execution_ids: List[uuid.UUID] = []

    # Create a test workflow with 3 steps
    workflow = WorkflowInstance(
        name="Test Execution Workflow",
        status=WorkflowStatus.PENDING.value,
    )
    for i in range(1, 4):
        step = WorkflowStep(
            name=f"Step {i}",
            step_order=i,
            status=StepStatus.PENDING.value,
        )
        workflow.steps.append(step)

    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    for step in workflow.steps:
        db.refresh(step)

    created_workflow_ids.append(workflow.id)

    yield db, workflow, created_execution_ids

    # Teardown: Clean up executions and workflows created during this test
    try:
        for exec_id in created_execution_ids:
            exec_steps = db.execute(
                select(ExecutionStep).where(ExecutionStep.execution_id == exec_id)
            ).scalars().all()
            for es in exec_steps:
                db.delete(es)
            db.commit()

            execution = db.get(WorkflowExecution, exec_id)
            if execution:
                db.delete(execution)
        db.commit()

        for wf_id in created_workflow_ids:
            wf = db.get(WorkflowInstance, wf_id)
            if wf:
                db.delete(wf)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# UNIT TESTS: Schema validation
# ---------------------------------------------------------------------------
class TestExecutionSchemaValidation:
    """Tests Pydantic validation for execution request schemas."""

    def test_valid_execution_request_no_failure(self):
        """An execution request without failure simulation is valid."""
        req = ExecutionRequest()
        assert req.failure_simulation is None

    def test_valid_execution_request_with_failure(self):
        """An execution request with a valid failure config is accepted."""
        req = ExecutionRequest(
            failure_simulation=FailureSimulationConfig(
                fail_at_step_order=2,
                error_message="Simulated payment gateway timeout",
            )
        )
        assert req.failure_simulation is not None
        assert req.failure_simulation.fail_at_step_order == 2
        assert "payment gateway" in req.failure_simulation.error_message

    def test_failure_config_requires_positive_step_order(self):
        """fail_at_step_order must be > 0."""
        with pytest.raises(ValidationError) as exc:
            FailureSimulationConfig(fail_at_step_order=0)
        assert "greater than 0" in str(exc.value).lower() or "gt" in str(exc.value).lower()

    def test_failure_config_rejects_negative_step_order(self):
        """Negative step_order is rejected."""
        with pytest.raises(ValidationError):
            FailureSimulationConfig(fail_at_step_order=-1)

    def test_execution_response_from_attributes(self):
        """ExecutionResponse can be built from ORM attributes."""
        assert ExecutionResponse.model_config.get("from_attributes") is True
        assert ExecutionStepResponse.model_config.get("from_attributes") is True


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: Execution service
# ---------------------------------------------------------------------------
class TestExecutionService:
    """Tests the execution service against the test database."""

    def test_successful_full_execution(self, test_workflow):
        """
        Executing a workflow without failure injection completes all steps.
        """
        db, workflow, created_exec_ids = test_workflow
        request = ExecutionRequest()

        result = execute_workflow(db, workflow.id, request)
        created_exec_ids.append(result.id)

        assert result.status == ExecutionStatus.COMPLETED.value
        assert result.attempt_number == 1
        assert result.trigger_type == "SIMULATED"
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.failure_reason is None
        assert result.failure_simulation_config is None

        assert len(result.execution_steps) == 3
        for i, exec_step in enumerate(result.execution_steps):
            assert exec_step.step_order == i + 1
            assert exec_step.status == ExecutionStepStatus.COMPLETED.value
            assert exec_step.started_at is not None
            assert exec_step.completed_at is not None
            assert exec_step.error_message is None
            assert exec_step.step_output is not None
            assert exec_step.step_output["simulated"] is True

    def test_injected_failure_at_step_2(self, test_workflow):
        """
        Injecting failure at step 2:
        - Step 1: COMPLETED
        - Step 2: FAILED with custom error message
        - Step 3: remains PENDING (no timestamps)
        - Execution: FAILED with failure_reason populated
        """
        db, workflow, created_exec_ids = test_workflow
        request = ExecutionRequest(
            failure_simulation=FailureSimulationConfig(
                fail_at_step_order=2,
                error_message="Simulated network timeout",
            )
        )

        result = execute_workflow(db, workflow.id, request)
        created_exec_ids.append(result.id)

        assert result.status == ExecutionStatus.FAILED.value
        assert result.failure_reason is not None
        assert "Simulated network timeout" in result.failure_reason
        assert result.completed_at is not None

        assert result.failure_simulation_config is not None
        assert result.failure_simulation_config["fail_at_step_order"] == 2

        steps = sorted(result.execution_steps, key=lambda s: s.step_order)
        assert len(steps) == 3

        assert steps[0].status == ExecutionStepStatus.COMPLETED.value
        assert steps[0].started_at is not None
        assert steps[0].completed_at is not None

        assert steps[1].status == ExecutionStepStatus.FAILED.value
        assert steps[1].started_at is not None
        assert steps[1].completed_at is not None
        assert steps[1].error_message == "Simulated network timeout"

        assert steps[2].status == ExecutionStepStatus.PENDING.value
        assert steps[2].started_at is None
        assert steps[2].completed_at is None

    def test_injected_failure_at_first_step(self, test_workflow):
        """
        Injecting failure at step 1:
        - Step 1: FAILED
        - Steps 2-3: remain PENDING
        - Execution: FAILED
        """
        db, workflow, created_exec_ids = test_workflow
        request = ExecutionRequest(
            failure_simulation=FailureSimulationConfig(
                fail_at_step_order=1,
            )
        )

        result = execute_workflow(db, workflow.id, request)
        created_exec_ids.append(result.id)

        assert result.status == ExecutionStatus.FAILED.value

        steps = sorted(result.execution_steps, key=lambda s: s.step_order)
        assert steps[0].status == ExecutionStepStatus.FAILED.value
        assert steps[1].status == ExecutionStepStatus.PENDING.value
        assert steps[2].status == ExecutionStepStatus.PENDING.value

    def test_repeated_execution_increments_attempt_number(self, test_workflow):
        """
        Running multiple executions on the same workflow produces
        monotonically increasing attempt_number values (1, 2, 3…).
        """
        db, workflow, created_exec_ids = test_workflow

        result1 = execute_workflow(db, workflow.id, ExecutionRequest())
        created_exec_ids.append(result1.id)
        assert result1.attempt_number == 1

        result2 = execute_workflow(db, workflow.id, ExecutionRequest())
        created_exec_ids.append(result2.id)
        assert result2.attempt_number == 2

        result3 = execute_workflow(
            db, workflow.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=1)
            ),
        )
        created_exec_ids.append(result3.id)
        assert result3.attempt_number == 3

    def test_invalid_failure_injection_rejected(self, test_workflow):
        """
        Specifying a fail_at_step_order that does not exist in the workflow
        raises InvalidFailureConfigError and creates NO execution record.
        """
        db, workflow, created_exec_ids = test_workflow
        request = ExecutionRequest(
            failure_simulation=FailureSimulationConfig(fail_at_step_order=99)
        )

        with pytest.raises(InvalidFailureConfigError) as exc:
            execute_workflow(db, workflow.id, request)

        assert "step_order=99" in str(exc.value)

        exec_count_stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow.id)
        )
        executions = list(db.execute(exec_count_stmt).scalars().all())
        assert len(executions) == 0

    def test_nonexistent_workflow_rejected(self):
        """
        Executing a nonexistent workflow raises WorkflowNotFoundError.
        """
        db = TestingSessionLocal()
        try:
            fake_id = uuid.uuid4()
            with pytest.raises(WorkflowNotFoundError) as exc:
                execute_workflow(db, fake_id, ExecutionRequest())
            assert str(fake_id) in str(exc.value)
        finally:
            db.close()

    def test_active_execution_conflict(self, test_workflow):
        """
        Starting a new execution while one is still PENDING or RUNNING
        raises ActiveExecutionConflictError.
        """
        db, workflow, created_exec_ids = test_workflow

        running_execution = WorkflowExecution(
            workflow_id=workflow.id,
            attempt_number=1,
            status=ExecutionStatus.RUNNING.value,
            trigger_type="SIMULATED",
        )
        db.add(running_execution)
        db.commit()
        db.refresh(running_execution)
        created_exec_ids.append(running_execution.id)

        with pytest.raises(ActiveExecutionConflictError) as exc:
            execute_workflow(db, workflow.id, ExecutionRequest())
        assert "already has an active execution" in str(exc.value)

    def test_get_execution_by_id_success(self, test_workflow):
        """
        get_execution_by_id returns the execution with steps eagerly loaded.
        """
        db, workflow, created_exec_ids = test_workflow

        result = execute_workflow(db, workflow.id, ExecutionRequest())
        created_exec_ids.append(result.id)

        fetched = get_execution_by_id(db, result.id)
        assert fetched is not None
        assert fetched.id == result.id
        assert fetched.workflow_id == workflow.id
        assert len(fetched.execution_steps) == 3

    def test_get_execution_by_id_not_found(self):
        """
        get_execution_by_id returns None for a nonexistent UUID.
        """
        db = TestingSessionLocal()
        try:
            result = get_execution_by_id(db, uuid.uuid4())
            assert result is None
        finally:
            db.close()

    def test_workflow_step_fields_not_overwritten(self, test_workflow):
        """
        After execution, the original WorkflowStep rows retain their
        original status and no runtime fields are modified.
        """
        db, workflow, created_exec_ids = test_workflow

        result = execute_workflow(db, workflow.id, ExecutionRequest())
        created_exec_ids.append(result.id)

        db.expire_all()
        fresh_workflow = db.get(WorkflowInstance, workflow.id)
        for step in fresh_workflow.steps:
            db.refresh(step)
            assert step.status == StepStatus.PENDING.value
            assert step.error_message is None

    def test_execution_with_default_failure_message(self, test_workflow):
        """
        When failure_simulation omits error_message, a default message is used.
        """
        db, workflow, created_exec_ids = test_workflow

        request = ExecutionRequest(
            failure_simulation=FailureSimulationConfig(
                fail_at_step_order=3,
            )
        )
        result = execute_workflow(db, workflow.id, request)
        created_exec_ids.append(result.id)

        steps = sorted(result.execution_steps, key=lambda s: s.step_order)
        assert steps[0].status == ExecutionStepStatus.COMPLETED.value
        assert steps[1].status == ExecutionStepStatus.COMPLETED.value
        assert steps[2].status == ExecutionStepStatus.FAILED.value
        assert "UNDOX failure simulation" in steps[2].error_message


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: Execution REST API Endpoints
# ---------------------------------------------------------------------------
class TestExecutionAPI:
    """Tests REST API endpoints for workflow execution and inspection."""

    def test_trigger_execution_success(self, test_workflow):
        """POST /workflows/{id}/execute runs workflow to COMPLETED status."""
        _, workflow, created_exec_ids = test_workflow

        response = client.post(f"/workflows/{workflow.id}/execute")
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        created_exec_ids.append(uuid.UUID(data["id"]))

        assert data["workflow_id"] == str(workflow.id)
        assert data["status"] == ExecutionStatus.COMPLETED.value
        assert data["attempt_number"] == 1
        assert data["trigger_type"] == "SIMULATED"
        assert len(data["execution_steps"]) == 3
        for step in data["execution_steps"]:
            assert step["status"] == ExecutionStepStatus.COMPLETED.value
            assert step["step_output"]["simulated"] is True

    def test_trigger_execution_with_failure_simulation(self, test_workflow):
        """POST /workflows/{id}/execute with failure simulation halts at target step."""
        _, workflow, created_exec_ids = test_workflow

        payload = {
            "failure_simulation": {
                "fail_at_step_order": 2,
                "error_message": "Network timeout during API test",
            }
        }
        response = client.post(f"/workflows/{workflow.id}/execute", json=payload)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        created_exec_ids.append(uuid.UUID(data["id"]))

        assert data["status"] == ExecutionStatus.FAILED.value
        assert "Network timeout during API test" in data["failure_reason"]

        steps = sorted(data["execution_steps"], key=lambda s: s["step_order"])
        assert steps[0]["status"] == ExecutionStepStatus.COMPLETED.value
        assert steps[1]["status"] == ExecutionStepStatus.FAILED.value
        assert steps[1]["error_message"] == "Network timeout during API test"
        assert steps[2]["status"] == ExecutionStepStatus.PENDING.value

    def test_trigger_execution_workflow_not_found(self):
        """POST /workflows/{id}/execute with unknown UUID returns HTTP 404."""
        non_existent_id = uuid.uuid4()
        response = client.post(f"/workflows/{non_existent_id}/execute")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"Workflow with ID '{non_existent_id}' not found" in response.json()["detail"]

    def test_trigger_execution_invalid_failure_config_returns_400(self, test_workflow):
        """POST /workflows/{id}/execute targeting nonexistent step returns HTTP 400."""
        _, workflow, _ = test_workflow

        payload = {"failure_simulation": {"fail_at_step_order": 99}}
        response = client.post(f"/workflows/{workflow.id}/execute", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot inject failure at step_order=99" in response.json()["detail"]

    def test_trigger_execution_invalid_uuid_returns_422(self):
        """POST /workflows/not-a-uuid/execute returns HTTP 422."""
        response = client.post("/workflows/invalid-uuid/execute")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_trigger_execution_invalid_payload_returns_422(self, test_workflow):
        """POST /workflows/{id}/execute with non-positive fail_at_step_order returns HTTP 422."""
        _, workflow, _ = test_workflow
        payload = {"failure_simulation": {"fail_at_step_order": 0}}
        response = client.post(f"/workflows/{workflow.id}/execute", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_execution_by_id_success(self, test_workflow):
        """GET /executions/{id} returns full execution details and step states."""
        _, workflow, created_exec_ids = test_workflow

        # Trigger execution first
        trigger_res = client.post(f"/workflows/{workflow.id}/execute")
        assert trigger_res.status_code == status.HTTP_201_CREATED
        exec_id = trigger_res.json()["id"]
        created_exec_ids.append(uuid.UUID(exec_id))

        # Retrieve execution
        get_res = client.get(f"/executions/{exec_id}")
        assert get_res.status_code == status.HTTP_200_OK
        data = get_res.json()
        assert data["id"] == exec_id
        assert data["workflow_id"] == str(workflow.id)
        assert data["status"] == ExecutionStatus.COMPLETED.value
        assert len(data["execution_steps"]) == 3

    def test_get_execution_not_found(self):
        """GET /executions/{id} with unknown UUID returns HTTP 404."""
        non_existent_id = uuid.uuid4()
        response = client.get(f"/executions/{non_existent_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"Execution with ID '{non_existent_id}' not found" in response.json()["detail"]

    def test_get_execution_invalid_uuid(self):
        """GET /executions/{id} with invalid UUID returns HTTP 422."""
        response = client.get("/executions/not-a-valid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# CONCURRENCY TESTS: PostgreSQL row-locking safety
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    TEST_DATABASE_URL.startswith("sqlite"),
    reason="Row-level locking concurrency tests require a PostgreSQL database",
)
class TestConcurrency:
    """
    Tests real concurrent PostgreSQL transaction behavior.
    Uses separate database sessions in separate threads to exercise
    the SELECT … FOR UPDATE row-level locking in _initialise_execution.
    """

    def test_concurrent_execution_attempts_one_wins(self):
        setup_db = TestingSessionLocal()
        workflow = WorkflowInstance(
            name="Concurrency Test Workflow",
            status=WorkflowStatus.PENDING.value,
        )
        for i in range(1, 3):
            workflow.steps.append(
                WorkflowStep(
                    name=f"Step {i}",
                    step_order=i,
                    status=StepStatus.PENDING.value,
                )
            )
        setup_db.add(workflow)
        setup_db.commit()
        setup_db.refresh(workflow)
        workflow_id = workflow.id
        setup_db.close()

        results = {"thread_1": None, "thread_2": None}
        errors = {"thread_1": None, "thread_2": None}
        barrier = threading.Barrier(2, timeout=10)

        def attempt_execution(thread_name: str):
            thread_db = TestingSessionLocal()
            try:
                barrier.wait()
                result = execute_workflow(
                    thread_db, workflow_id, ExecutionRequest()
                )
                results[thread_name] = result.id
            except (ActiveExecutionConflictError, Exception) as e:
                errors[thread_name] = e
            finally:
                thread_db.close()

        t1 = threading.Thread(target=attempt_execution, args=("thread_1",))
        t2 = threading.Thread(target=attempt_execution, args=("thread_2",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        successes = [k for k, v in results.items() if v is not None]
        conflicts = [
            k for k, v in errors.items()
            if isinstance(v, ActiveExecutionConflictError)
        ]

        assert len(successes) == 1
        assert len(conflicts) == 1

        cleanup_db = TestingSessionLocal()
        try:
            execs = list(
                cleanup_db.execute(
                    select(WorkflowExecution).where(
                        WorkflowExecution.workflow_id == workflow_id
                    )
                ).scalars().all()
            )
            for exc in execs:
                exec_steps = list(
                    cleanup_db.execute(
                        select(ExecutionStep).where(
                            ExecutionStep.execution_id == exc.id
                        )
                    ).scalars().all()
                )
                for es in exec_steps:
                    cleanup_db.delete(es)
                cleanup_db.delete(exc)
            cleanup_db.commit()

            wf = cleanup_db.get(WorkflowInstance, workflow_id)
            if wf:
                cleanup_db.delete(wf)
            cleanup_db.commit()
        except Exception:
            cleanup_db.rollback()
        finally:
            cleanup_db.close()
