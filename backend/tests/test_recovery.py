"""
Tests for the Failure Recovery Planning Engine in UNDOX.

Covers:
- Schema validation for RecoveryPlanRequest, RecoveryPlanResponse, and RecoveryPlanActionResponse.
- Recovery Planning Service:
  - Successful recovery planning for a failed execution (SAGA_COMPENSATE strategy).
  - LIFO compensation ordering for multiple completed steps.
  - Irreversible action detection via domain heuristics (e.g. emails, physical dispatch).
  - Irreversible action handling via explicit caller declaration (unsupported_steps).
  - Strict preservation of original execution history (zero mutation of executions or execution steps).
  - Error handling for nonexistent executions (ExecutionNotFoundError -> 404).
  - Error handling for non-failed executions (ExecutionNotFailedError -> 400).
  - Recovery plan retrieval by ID and listing plans by execution ID.
- Recovery REST API:
  - POST /executions/{id}/recovery-plans (201 Created, 404 Not Found, 400 Bad Request).
  - GET /recovery-plans/{id} (200 OK, 404 Not Found).
  - GET /executions/{id}/recovery-plans (200 OK list, 404 Not Found).
"""

import os
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
from backend.app.models.recovery import (
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryPlan,
    RecoveryPlanAction,
    RecoveryPlanStatus,
)
from backend.app.models.workflow import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from backend.app.executions.service import execute_workflow
from backend.app.recovery.service import (
    ExecutionNotFailedError,
    ExecutionNotFoundError,
    generate_recovery_plan,
    get_recovery_plan_by_id,
    list_recovery_plans_for_execution,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig
from backend.app.schemas.recovery import (
    RecoveryPlanActionResponse,
    RecoveryPlanRequest,
    RecoveryPlanResponse,
)

# ---------------------------------------------------------------------------
# Test database setup (in-memory SQLite with StaticPool)
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
    """Ensure the FastAPI application uses the test database for all endpoints."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper fixture: Create test workflows and track records for clean teardown
# ---------------------------------------------------------------------------
@pytest.fixture
def recovery_test_env() -> Generator:
    """
    Sets up a clean database session and tracks created workflow, execution,
    and recovery plan IDs to clean up thoroughly in teardown.
    """
    db = TestingSessionLocal()
    created_workflows: List[uuid.UUID] = []
    created_executions: List[uuid.UUID] = []
    created_plans: List[uuid.UUID] = []

    def create_workflow(step_names: List[str]) -> WorkflowInstance:
        wf = WorkflowInstance(
            name="Recovery Test Workflow",
            status=WorkflowStatus.PENDING.value,
        )
        for idx, name in enumerate(step_names, start=1):
            s = WorkflowStep(
                name=name,
                step_order=idx,
                status=StepStatus.PENDING.value,
            )
            wf.steps.append(s)
        db.add(wf)
        db.commit()
        db.refresh(wf)
        created_workflows.append(wf.id)
        return wf

    yield db, create_workflow, created_executions, created_plans

    # Teardown
    try:
        for plan_id in created_plans:
            plan_actions = db.execute(
                select(RecoveryPlanAction).where(RecoveryPlanAction.plan_id == plan_id)
            ).scalars().all()
            for pa in plan_actions:
                db.delete(pa)
            plan = db.get(RecoveryPlan, plan_id)
            if plan:
                db.delete(plan)
        db.commit()

        for exec_id in created_executions:
            exec_steps = db.execute(
                select(ExecutionStep).where(ExecutionStep.execution_id == exec_id)
            ).scalars().all()
            for es in exec_steps:
                db.delete(es)
            execution = db.get(WorkflowExecution, exec_id)
            if execution:
                db.delete(execution)
        db.commit()

        for wf_id in created_workflows:
            wf = db.get(WorkflowInstance, wf_id)
            if wf:
                db.delete(wf)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# UNIT TESTS: Schema Validation
# ---------------------------------------------------------------------------
class TestRecoverySchemaValidation:
    """Verifies Pydantic DTO validation for recovery planning schemas."""

    def test_default_recovery_request_schema(self):
        """Default request has empty unsupported_steps and strategy=None."""
        req = RecoveryPlanRequest()
        assert req.strategy is None
        assert req.unsupported_steps == []

    def test_custom_recovery_request_schema(self):
        """Request accepts custom strategy and list of unsupported step orders."""
        req = RecoveryPlanRequest(
            strategy="SAGA_COMPENSATE",
            unsupported_steps=[1, 3],
        )
        assert req.strategy == "SAGA_COMPENSATE"
        assert req.unsupported_steps == [1, 3]

    def test_unsupported_steps_must_be_positive(self):
        """Step orders in unsupported_steps must be greater than 0."""
        with pytest.raises(ValidationError):
            RecoveryPlanRequest(unsupported_steps=[0])

        with pytest.raises(ValidationError):
            RecoveryPlanRequest(unsupported_steps=[-2])


# ---------------------------------------------------------------------------
# UNIT TESTS: Recovery Planning Service
# ---------------------------------------------------------------------------
class TestRecoveryPlanningService:
    """Verifies core recovery planning analysis, LIFO compensation, and rules."""

    def test_successful_recovery_plan_generation(self, recovery_test_env):
        """
        Given a failed execution (Step 1 COMPLETED, Step 2 FAILED, Step 3 PENDING),
        When a recovery plan is generated,
        Then:
          - A plan with a unique ID and GENERATED status is created.
          - Strategy is SAGA_COMPENSATE.
          - Action 1: COMPENSATE for Step 1 (reversible, simulated).
          - Action 2: RETRY for Step 2.
          - Action 3: SKIP for Step 3.
          - requires_manual_approval is False.
        """
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Reserve Inventory", "Process Payment", "Update Account"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(
                    fail_at_step_order=2,
                    error_message="Payment gateway timeout",
                )
            ),
        )
        created_executions.append(exec_record.id)
        assert exec_record.status == ExecutionStatus.FAILED.value

        # Generate recovery plan
        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        assert plan.id is not None
        assert plan.execution_id == exec_record.id
        assert plan.workflow_id == wf.id
        assert plan.status == RecoveryPlanStatus.GENERATED.value
        assert plan.strategy == "SAGA_COMPENSATE"
        assert not plan.requires_manual_approval
        assert len(plan.actions) == 3

        # Action 1: Compensate Step 1
        act1 = plan.actions[0]
        assert act1.action_order == 1
        assert act1.target_step_order == 1
        assert act1.target_step_name == "Reserve Inventory"
        assert act1.action_type == RecoveryActionType.COMPENSATE.value
        assert act1.status == RecoveryActionStatus.PROPOSED.value
        assert act1.is_reversible is True
        assert "simulated" in act1.explanation.lower()
        assert act1.compensation_details is not None
        assert act1.compensation_details.get("simulated") is True
        assert act1.compensation_details.get("original_step_name") == "Reserve Inventory"

        # Action 2: Retry Step 2
        act2 = plan.actions[1]
        assert act2.action_order == 2
        assert act2.target_step_order == 2
        assert act2.target_step_name == "Process Payment"
        assert act2.action_type == RecoveryActionType.RETRY.value
        assert act2.status == RecoveryActionStatus.PROPOSED.value
        assert act2.is_reversible is True
        assert "retry" in act2.explanation.lower()

        # Action 3: Skip Step 3
        act3 = plan.actions[2]
        assert act3.action_order == 3
        assert act3.target_step_order == 3
        assert act3.target_step_name == "Update Account"
        assert act3.action_type == RecoveryActionType.SKIP.value
        assert act3.status == RecoveryActionStatus.PROPOSED.value
        assert act3.is_reversible is True
        assert "never attempted" in act3.explanation.lower() or "pending" in act3.explanation.lower()

    def test_lifo_ordering_for_multiple_completed_steps(self, recovery_test_env):
        """
        When multiple steps succeed before a failure,
        the compensation actions must be proposed in reverse (LIFO) order.
        """
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow([
            "Validate Token",
            "Reserve Funds",
            "Debit Ledger",
            "Call Third-Party API",  # will fail
            "Send Confirmation",
        ])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(
                    fail_at_step_order=4,
                    error_message="Third party connection reset",
                )
            ),
        )
        created_executions.append(exec_record.id)

        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        # 3 completed steps (1, 2, 3), 1 failed (4), 1 pending (5) -> Total 5 actions
        assert len(plan.actions) == 5

        # LIFO check for compensation: Step 3 first, then Step 2, then Step 1
        assert plan.actions[0].target_step_order == 3
        assert plan.actions[0].target_step_name == "Debit Ledger"
        assert plan.actions[0].action_type == RecoveryActionType.COMPENSATE.value

        assert plan.actions[1].target_step_order == 2
        assert plan.actions[1].target_step_name == "Reserve Funds"
        assert plan.actions[1].action_type == RecoveryActionType.COMPENSATE.value

        assert plan.actions[2].target_step_order == 1
        assert plan.actions[2].target_step_name == "Validate Token"
        assert plan.actions[2].action_type == RecoveryActionType.COMPENSATE.value

        # Then retry failed step 4
        assert plan.actions[3].target_step_order == 4
        assert plan.actions[3].action_type == RecoveryActionType.RETRY.value

        # Then skip pending step 5
        assert plan.actions[4].target_step_order == 5
        assert plan.actions[4].action_type == RecoveryActionType.SKIP.value

    def test_unsupported_compensation_by_heuristic(self, recovery_test_env):
        """
        Completed steps with irreversible characteristics (e.g. email, notification, dispatch)
        must NOT be automatically compensated. They must be flagged as requiring manual review.
        """
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow([
            "Send Email Notification",  # Irreversible side-effect
            "Process Payment",         # Will fail
            "Deliver Order",
        ])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        # Plan-level flags
        assert plan.requires_manual_approval is True
        assert plan.strategy == "MANUAL_REVIEW"

        # Action-level check for Step 1
        email_action = plan.actions[0]
        assert email_action.target_step_order == 1
        assert email_action.is_reversible is False
        assert email_action.action_type == RecoveryActionType.MANUAL_REVIEW.value
        assert email_action.status == RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value
        assert "irreversible" in email_action.explanation.lower()
        assert "manual" in email_action.explanation.lower()

    def test_unsupported_compensation_by_explicit_caller_request(self, recovery_test_env):
        """
        Callers can explicitly declare steps as unsupported/irreversible in RecoveryPlanRequest.
        These steps must be marked for manual review.
        """
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Prepare Package", "Charge Card", "Ship Item"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        plan = generate_recovery_plan(
            db,
            exec_record.id,
            RecoveryPlanRequest(unsupported_steps=[1]),
        )
        created_plans.append(plan.id)

        assert plan.requires_manual_approval is True
        act1 = plan.actions[0]
        assert act1.target_step_order == 1
        assert act1.is_reversible is False
        assert act1.status == RecoveryActionStatus.REQUIRES_MANUAL_REVIEW.value

    def test_preservation_of_original_execution_history(self, recovery_test_env):
        """
        CRITICAL: Generating a recovery plan must NEVER mutate or alter the original
        WorkflowExecution or ExecutionStep records. The historical audit trail is preserved intact.
        """
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Step A", "Step B", "Step C"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(
                    fail_at_step_order=2,
                    error_message="Fatal network disconnect",
                )
            ),
        )
        created_executions.append(exec_record.id)

        # Snapshot execution and step states prior to recovery planning
        orig_exec_status = exec_record.status
        orig_attempt_number = exec_record.attempt_number
        orig_failure_reason = exec_record.failure_reason
        orig_started_at = exec_record.started_at
        orig_completed_at = exec_record.completed_at

        orig_steps = [
            {
                "id": s.id,
                "step_order": s.step_order,
                "status": s.status,
                "error_message": s.error_message,
                "completed_at": s.completed_at,
            }
            for s in exec_record.execution_steps
        ]

        # Generate the recovery plan
        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        # Refresh execution record from database to verify no in-place mutation
        db.refresh(exec_record)

        assert exec_record.status == orig_exec_status == ExecutionStatus.FAILED.value
        assert exec_record.attempt_number == orig_attempt_number
        assert exec_record.failure_reason == orig_failure_reason
        assert exec_record.started_at == orig_started_at
        assert exec_record.completed_at == orig_completed_at

        # Verify steps remain completely unchanged
        for orig_s, curr_s in zip(orig_steps, exec_record.execution_steps):
            assert curr_s.id == orig_s["id"]
            assert curr_s.step_order == orig_s["step_order"]
            assert curr_s.status == orig_s["status"]
            assert curr_s.error_message == orig_s["error_message"]
            assert curr_s.completed_at == orig_s["completed_at"]

    def test_missing_execution_raises_not_found(self, recovery_test_env):
        """Requesting recovery for a nonexistent execution ID raises ExecutionNotFoundError."""
        db, _, _, _ = recovery_test_env
        missing_id = uuid.uuid4()

        with pytest.raises(ExecutionNotFoundError) as exc_info:
            generate_recovery_plan(db, missing_id)

        assert str(missing_id) in str(exc_info.value)

    def test_non_failed_execution_raises_error(self, recovery_test_env):
        """Attempting to generate a recovery plan for a COMPLETED execution is rejected."""
        db, create_workflow, created_executions, _ = recovery_test_env

        wf = create_workflow(["Step A", "Step B"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)
        assert exec_record.status == ExecutionStatus.COMPLETED.value

        with pytest.raises(ExecutionNotFailedError) as exc_info:
            generate_recovery_plan(db, exec_record.id)

        assert "COMPLETED" in str(exc_info.value)
        assert "FAILED" in str(exc_info.value)

    def test_get_and_list_recovery_plans(self, recovery_test_env):
        """Verifies querying plans by ID and listing plans for a workflow execution."""
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        plan1 = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan1.id)

        plan2 = generate_recovery_plan(
            db,
            exec_record.id,
            RecoveryPlanRequest(strategy="RETRY_FAILED_ONLY"),
        )
        created_plans.append(plan2.id)

        # Fetch plan by ID
        fetched = get_recovery_plan_by_id(db, plan1.id)
        assert fetched is not None
        assert fetched.id == plan1.id
        assert len(fetched.actions) == len(plan1.actions)

        # Nonexistent plan returns None
        assert get_recovery_plan_by_id(db, uuid.uuid4()) is None

        # List plans for execution
        plans_list = list_recovery_plans_for_execution(db, exec_record.id)
        assert len(plans_list) == 2
        plan_ids = [p.id for p in plans_list]
        assert plan1.id in plan_ids
        assert plan2.id in plan_ids


# ---------------------------------------------------------------------------
# API TESTS: Recovery REST API
# ---------------------------------------------------------------------------
class TestRecoveryAPI:
    """Verifies REST endpoints for recovery planning."""

    def test_create_recovery_plan_api_success(self, recovery_test_env):
        """POST /executions/{id}/recovery-plans creates and returns a recovery plan with 201."""
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Step 1", "Step 2", "Step 3"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        resp = client.post(
            f"/executions/{exec_record.id}/recovery-plans",
            json={"unsupported_steps": []},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        assert "id" in data
        created_plans.append(uuid.UUID(data["id"]))
        assert data["execution_id"] == str(exec_record.id)
        assert data["workflow_id"] == str(wf.id)
        assert data["status"] == "GENERATED"
        assert len(data["actions"]) == 3
        assert data["actions"][0]["action_type"] == "COMPENSATE"
        assert data["actions"][1]["action_type"] == "RETRY"
        assert data["actions"][2]["action_type"] == "SKIP"

    def test_create_recovery_plan_api_not_found(self):
        """POST /executions/{id}/recovery-plans returns 404 for nonexistent execution ID."""
        missing_id = uuid.uuid4()
        resp = client.post(
            f"/executions/{missing_id}/recovery-plans",
            json={},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in resp.json()["detail"].lower()

    def test_create_recovery_plan_api_non_failed_execution(self, recovery_test_env):
        """POST /executions/{id}/recovery-plans returns 400 when execution did not fail."""
        db, create_workflow, created_executions, _ = recovery_test_env

        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)
        assert exec_record.status == ExecutionStatus.COMPLETED.value

        resp = client.post(
            f"/executions/{exec_record.id}/recovery-plans",
            json={},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "failed" in resp.json()["detail"].lower()

    def test_get_recovery_plan_by_id_api(self, recovery_test_env):
        """GET /recovery-plans/{id} retrieves the plan and actions, or returns 404."""
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        # Successful retrieval
        resp = client.get(f"/recovery-plans/{plan.id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["id"] == str(plan.id)
        assert len(data["actions"]) == len(plan.actions)

        # Nonexistent plan
        missing_id = uuid.uuid4()
        resp_missing = client.get(f"/recovery-plans/{missing_id}")
        assert resp_missing.status_code == status.HTTP_404_NOT_FOUND

    def test_list_recovery_plans_for_execution_api(self, recovery_test_env):
        """GET /executions/{id}/recovery-plans lists all plans for an execution."""
        db, create_workflow, created_executions, created_plans = recovery_test_env

        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        # Before generating plans -> returns empty list []
        resp_empty = client.get(f"/executions/{exec_record.id}/recovery-plans")
        assert resp_empty.status_code == status.HTTP_200_OK
        assert resp_empty.json() == []

        # Generate a plan
        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)

        # After generating plan -> returns list with plan
        resp_list = client.get(f"/executions/{exec_record.id}/recovery-plans")
        assert resp_list.status_code == status.HTTP_200_OK
        data = resp_list.json()
        assert len(data) == 1
        assert data[0]["id"] == str(plan.id)

        # Nonexistent execution returns 404
        missing_id = uuid.uuid4()
        resp_missing = client.get(f"/executions/{missing_id}/recovery-plans")
        assert resp_missing.status_code == status.HTTP_404_NOT_FOUND
