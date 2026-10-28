"""
Tests for the Recovery Execution Engine in UNDOX.

Covers:
- Controlled execution of approved recovery plans using simulated actions.
- Recovery plan lifecycle transitions: GENERATED -> APPROVED -> EXECUTING -> COMPLETED / FAILED / REJECTED.
- Tracking of individual recovery action statuses and simulation details.
- Action execution strictly following plan action_order.
- Manual-review / irreversible action authorization enforcement.
- Duplicate execution prevention (completed or actively executing plans).
- Safe action failure handling (halting downstream actions and marking plan FAILED).
- Conflict and staleness integration blocking stale plan execution.
- Strict preservation of original WorkflowExecution history.
- REST API endpoints:
  - POST /recovery-plans/{id}/approve
  - POST /recovery-plans/{id}/reject
  - POST /recovery-plans/{id}/execute
  - GET /recovery-plans/{id}/execution-status
"""

import os
import uuid
from typing import Generator, List

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.executions.service import execute_workflow
from backend.app.main import app
from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
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
from backend.app.recovery.executor import (
    approve_recovery_plan,
    execute_recovery_plan,
    get_recovery_execution_status,
    reject_recovery_plan,
)
from backend.app.recovery.service import (
    RecoveryPlanExecutionConflictError,
    RecoveryPlanNotApprovedError,
    RecoveryPlanNotFoundError,
    RecoveryPlanStaleError,
    RecoveryPlanUnauthorizedActionError,
    generate_recovery_plan,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig
from backend.app.schemas.recovery import (
    RecoveryExecutionRequest,
    RecoveryPlanApprovalRequest,
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
# Fixture for workflow, execution, and plan management
# ---------------------------------------------------------------------------
@pytest.fixture
def executor_test_env() -> Generator:
    """
    Sets up a database session and tracks created workflow, execution,
    and recovery plan IDs to clean up thoroughly in teardown.
    """
    db = TestingSessionLocal()
    created_workflows: List[uuid.UUID] = []
    created_executions: List[uuid.UUID] = []
    created_plans: List[uuid.UUID] = []

    def create_workflow(step_names: List[str]) -> WorkflowInstance:
        wf = WorkflowInstance(
            name="Executor Test Workflow",
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
# UNIT TESTS: Recovery Execution Engine Service
# ---------------------------------------------------------------------------
class TestRecoveryExecutionService:
    """Tests the recovery execution engine service logic."""

    def test_successful_full_recovery_execution(self, executor_test_env):
        """
        An approved recovery plan executes all actions in defined order,
        transitions to COMPLETED, and reconciles workflow status to RECOVERED.
        """
        db, create_workflow, created_executions, created_plans = executor_test_env

        wf = create_workflow(["Reserve Seats", "Charge Card", "Issue Ticket"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)
        assert exec_record.status == ExecutionStatus.FAILED.value

        # Snapshot original execution state to verify immutability
        orig_started_at = exec_record.started_at
        orig_completed_at = exec_record.completed_at
        orig_attempt_number = exec_record.attempt_number
        orig_failure_reason = exec_record.failure_reason

        # Generate recovery plan
        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)
        assert plan.status == RecoveryPlanStatus.GENERATED.value

        # Approve plan
        approved_plan = approve_recovery_plan(db, plan.id)
        assert approved_plan.status == RecoveryPlanStatus.APPROVED.value

        # Execute plan
        completed_plan = execute_recovery_plan(db, plan.id)
        assert completed_plan.status == RecoveryPlanStatus.COMPLETED.value

        # Verify all actions completed in order
        for action in completed_plan.actions:
            assert action.status == RecoveryActionStatus.COMPLETED.value
            assert action.compensation_details is not None
            res = action.compensation_details.get("execution_result")
            assert res is not None
            assert res.get("status") == "COMPLETED"
            assert res.get("simulated") is True

        # Workflow status reconciled to RECOVERED
        db.refresh(wf)
        assert wf.status == WorkflowStatus.RECOVERED.value

        # Verify strict immutability of original execution history
        db.refresh(exec_record)
        assert exec_record.status == ExecutionStatus.FAILED.value
        assert exec_record.started_at == orig_started_at
        assert exec_record.completed_at == orig_completed_at
        assert exec_record.attempt_number == orig_attempt_number
        assert exec_record.failure_reason == orig_failure_reason

    def test_simulated_action_failure_halts_execution(self, executor_test_env):
        """
        When a recovery action fails, execution halts immediately:
        - Failed action marked FAILED with error details.
        - Downstream actions marked SKIPPED.
        - Plan status marked FAILED.
        - Original execution history remains untouched.
        """
        db, create_workflow, created_executions, created_plans = executor_test_env

        wf = create_workflow(["Step 1", "Step 2", "Step 3", "Step 4"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=3)
            ),
        )
        created_executions.append(exec_record.id)

        plan = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan.id)
        approve_recovery_plan(db, plan.id)

        # Execute with simulated failure at action order 1
        result_plan = execute_recovery_plan(
            db,
            plan.id,
            RecoveryExecutionRequest(
                simulate_action_failure_at_order=1,
                simulated_error_message="Simulated compensation rollback failure",
            ),
        )

        assert result_plan.status == RecoveryPlanStatus.FAILED.value

        # Action 1 failed
        act1 = result_plan.actions[0]
        assert act1.action_order == 1
        assert act1.status == RecoveryActionStatus.FAILED.value
        res1 = act1.compensation_details.get("execution_result")
        assert res1["status"] == "FAILED"
        assert res1["error"] == "Simulated compensation rollback failure"

        # Subsequent actions skipped
        for downstream in result_plan.actions[1:]:
            assert downstream.status == RecoveryActionStatus.SKIPPED.value
            res = downstream.compensation_details.get("execution_result")
            assert res["status"] == "SKIPPED"

        # Workflow status should NOT be RECOVERED
        db.refresh(wf)
        assert wf.status != WorkflowStatus.RECOVERED.value

    def test_unapproved_plan_cannot_execute(self, executor_test_env):
        """Executing a plan in GENERATED status raises RecoveryPlanNotApprovedError."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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
        assert plan.status == RecoveryPlanStatus.GENERATED.value

        with pytest.raises(RecoveryPlanNotApprovedError) as exc_info:
            execute_recovery_plan(db, plan.id)

        assert "APPROVED" in str(exc_info.value)

    def test_duplicate_execution_prevention(self, executor_test_env):
        """A completed recovery plan cannot be re-executed."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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
        approve_recovery_plan(db, plan.id)
        execute_recovery_plan(db, plan.id)

        # Attempt second execution
        with pytest.raises(RecoveryPlanExecutionConflictError) as exc_info:
            execute_recovery_plan(db, plan.id)

        assert "already been executed" in str(exc_info.value).lower()

    def test_stale_plan_cannot_execute(self, executor_test_env):
        """
        If the execution state changes after plan approval (e.g. execution transitions to COMPLETED),
        executing the plan is blocked as stale.
        """
        db, create_workflow, created_executions, created_plans = executor_test_env

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
        approve_recovery_plan(db, plan.id)

        # Execution subsequently transitions to COMPLETED
        exec_record.status = ExecutionStatus.COMPLETED.value
        db.commit()

        with pytest.raises(RecoveryPlanStaleError) as exc_info:
            execute_recovery_plan(db, plan.id)

        assert "stale" in str(exc_info.value).lower()

    def test_manual_review_approval_enforcement(self, executor_test_env):
        """
        Plans with irreversible steps cannot be approved without explicit authorization.
        Once explicitly authorized, they execute cleanly.
        """
        db, create_workflow, created_executions, created_plans = executor_test_env

        wf = create_workflow(["Send Email Notification", "Debit Account"])
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
        assert plan.requires_manual_approval is True

        # Unapproved attempt fails
        with pytest.raises(RecoveryPlanUnauthorizedActionError) as exc_info:
            approve_recovery_plan(db, plan.id, RecoveryPlanApprovalRequest(authorize_manual_review=False))

        assert "authorize_manual_review=True" in str(exc_info.value)

        # Explicitly authorized approval succeeds
        approved = approve_recovery_plan(
            db,
            plan.id,
            RecoveryPlanApprovalRequest(authorize_manual_review=True, notes="Operator verified email log"),
        )
        assert approved.status == RecoveryPlanStatus.APPROVED.value
        assert approved.requires_manual_approval is False

        # Executes successfully
        completed = execute_recovery_plan(db, plan.id)
        assert completed.status == RecoveryPlanStatus.COMPLETED.value

    def test_reject_recovery_plan(self, executor_test_env):
        """Rejecting a plan sets its status to REJECTED and blocks execution."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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

        rejected = reject_recovery_plan(db, plan.id, notes="Operator rejected plan")
        assert rejected.status == RecoveryPlanStatus.REJECTED.value

        with pytest.raises(RecoveryPlanNotApprovedError):
            execute_recovery_plan(db, plan.id)

    def test_get_execution_status_metrics(self, executor_test_env):
        """get_recovery_execution_status returns progress counts."""
        db, create_workflow, created_executions, created_plans = executor_test_env

        wf = create_workflow(["Step 1", "Step 2", "Step 3"])
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

        # Before execution
        status_before = get_recovery_execution_status(db, plan.id)
        assert status_before.status == RecoveryPlanStatus.GENERATED.value
        assert status_before.total_actions == 3
        assert status_before.completed_actions == 0
        assert status_before.pending_actions == 3

        # After execution
        approve_recovery_plan(db, plan.id)
        execute_recovery_plan(db, plan.id)

        status_after = get_recovery_execution_status(db, plan.id)
        assert status_after.status == RecoveryPlanStatus.COMPLETED.value
        assert status_after.completed_actions == 3
        assert status_after.failed_actions == 0
        assert status_after.pending_actions == 0


# ---------------------------------------------------------------------------
# API TESTS: Recovery Execution Endpoints
# ---------------------------------------------------------------------------
class TestRecoveryExecutionAPI:
    """Tests API routes for approving, rejecting, executing, and monitoring recovery plans."""

    def test_api_approve_and_execute_plan_success(self, executor_test_env):
        """Full API flow: approve -> execute -> get execution status."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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

        # 1. Approve plan
        resp_approve = client.post(
            f"/recovery-plans/{plan.id}/approve",
            json={"authorize_manual_review": False},
        )
        assert resp_approve.status_code == status.HTTP_200_OK
        assert resp_approve.json()["status"] == "APPROVED"

        # 2. Execute plan
        resp_exec = client.post(
            f"/recovery-plans/{plan.id}/execute",
            json={},
        )
        assert resp_exec.status_code == status.HTTP_200_OK
        data_exec = resp_exec.json()
        assert data_exec["status"] == "COMPLETED"
        assert all(a["status"] == "COMPLETED" for a in data_exec["actions"])

        # 3. Get execution status
        resp_status = client.get(f"/recovery-plans/{plan.id}/execution-status")
        assert resp_status.status_code == status.HTTP_200_OK
        data_status = resp_status.json()
        assert data_status["status"] == "COMPLETED"
        assert data_status["completed_actions"] == len(data_exec["actions"])
        assert data_status["failed_actions"] == 0

    def test_api_execute_unapproved_plan_returns_400(self, executor_test_env):
        """POST /recovery-plans/{id}/execute returns 400 for unapproved plans."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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

        resp = client.post(f"/recovery-plans/{plan.id}/execute", json={})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "approved" in resp.json()["detail"].lower()

    def test_api_execute_missing_plan_returns_404(self):
        """POST /recovery-plans/{id}/execute returns 404 for nonexistent plan ID."""
        missing_id = uuid.uuid4()
        resp = client.post(f"/recovery-plans/{missing_id}/execute", json={})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_api_reject_plan(self, executor_test_env):
        """POST /recovery-plans/{id}/reject sets plan status to REJECTED."""
        db, create_workflow, created_executions, created_plans = executor_test_env

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

        resp = client.post(f"/recovery-plans/{plan.id}/reject")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "REJECTED"

    def test_api_simulated_action_failure(self, executor_test_env):
        """POST /recovery-plans/{id}/execute with simulated failure halts execution."""
        db, create_workflow, created_executions, created_plans = executor_test_env

        wf = create_workflow(["Step 1", "Step 2", "Step 3"])
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

        # Approve
        client.post(f"/recovery-plans/{plan.id}/approve")

        # Execute with failure at action 1
        resp = client.post(
            f"/recovery-plans/{plan.id}/execute",
            json={
                "simulate_action_failure_at_order": 1,
                "simulated_error_message": "Rollback failed via API simulation",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "FAILED"
        assert data["actions"][0]["status"] == "FAILED"
