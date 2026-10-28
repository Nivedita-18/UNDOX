"""
Tests for the Operator Approval and Rejection System in UNDOX.

Covers:
- Explicit approval workflows for recovery plans (with and without manual review authorization).
- Explicit rejection workflows with operator reasons and audit logging.
- Enforcement that plans requiring manual review must not execute before approval.
- Stale plan detection during approval, resulting in auto-rejection and blocking execution.
- Unresolved blocking conflicts during approval, resulting in auto-rejection and blocking execution.
- Storing approval/rejection decisions, operators, timestamps, and reasons.
- Prevention of duplicate approval or rejection decisions (409 Conflict).
- Prevention of contradictory approval/rejection decisions (409 Conflict).
- Strict enforcement that rejected plans cannot execute.
- Strict preservation of original WorkflowExecution and ExecutionStep history.
- REST API tests:
  - POST /recovery-plans/{id}/approve
  - POST /recovery-plans/{id}/reject
  - POST /recovery-plans/{id}/execute
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
    reject_recovery_plan,
)
from backend.app.recovery.service import (
    RecoveryPlanDuplicateDecisionError,
    RecoveryPlanExecutionConflictError,
    RecoveryPlanNotApprovedError,
    RecoveryPlanNotFoundError,
    RecoveryPlanStaleError,
    RecoveryPlanUnauthorizedActionError,
    generate_recovery_plan,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig
from backend.app.schemas.recovery import (
    RecoveryPlanApprovalRequest,
    RecoveryPlanRejectionRequest,
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
def approval_test_env() -> Generator:
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
            name="Approval Test Workflow",
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
# UNIT TESTS: Approval & Rejection Logic
# ---------------------------------------------------------------------------
class TestOperatorApprovalRejectionService:
    """Tests approval, rejection, decision logging, and guardrails."""

    def test_approve_plan_stores_decision_and_reason(self, approval_test_env):
        """
        Approving a plan updates status to APPROVED, logs the operator identity,
        records the approval reason, and sets decided_at.
        """
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # Approve with explicit operator and reason
        approved_plan = approve_recovery_plan(
            db,
            plan.id,
            RecoveryPlanApprovalRequest(
                operator="lead_sre_alice",
                reason="Audit check verified that step 1 can be reversed safely",
            ),
        )

        assert approved_plan.status == RecoveryPlanStatus.APPROVED.value
        assert approved_plan.decision_operator == "lead_sre_alice"
        assert approved_plan.decision_reason == "Audit check verified that step 1 can be reversed safely"
        assert approved_plan.decided_at is not None
        assert "--- Operator Decision ---" in approved_plan.summary

    def test_reject_plan_stores_decision_and_reason(self, approval_test_env):
        """
        Rejecting a plan updates status to REJECTED, logs operator and reason,
        and ensures the plan cannot be executed.
        """
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        rejected_plan = reject_recovery_plan(
            db,
            plan.id,
            RecoveryPlanRejectionRequest(
                operator="lead_sre_bob",
                reason="Manual compensation via database patch preferred",
            ),
        )

        assert rejected_plan.status == RecoveryPlanStatus.REJECTED.value
        assert rejected_plan.decision_operator == "lead_sre_bob"
        assert rejected_plan.decision_reason == "Manual compensation via database patch preferred"
        assert rejected_plan.decided_at is not None

        # Ensure rejected plan cannot execute
        with pytest.raises(RecoveryPlanNotApprovedError) as exc_info:
            execute_recovery_plan(db, plan.id)

        assert "REJECTED" in str(exc_info.value)

    def test_duplicate_approval_rejected(self, approval_test_env):
        """Approving an already approved plan raises RecoveryPlanDuplicateDecisionError."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # First approval
        approve_recovery_plan(db, plan.id)

        # Second approval attempt
        with pytest.raises(RecoveryPlanDuplicateDecisionError) as exc_info:
            approve_recovery_plan(db, plan.id)

        assert "already been approved" in str(exc_info.value).lower()

    def test_duplicate_rejection_rejected(self, approval_test_env):
        """Rejecting an already rejected plan raises RecoveryPlanDuplicateDecisionError."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # First rejection
        reject_recovery_plan(db, plan.id)

        # Second rejection attempt
        with pytest.raises(RecoveryPlanDuplicateDecisionError) as exc_info:
            reject_recovery_plan(db, plan.id)

        assert "already been rejected" in str(exc_info.value).lower()

    def test_contradictory_approval_of_rejected_plan_prevented(self, approval_test_env):
        """Attempting to approve a plan that was previously rejected is blocked."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        reject_recovery_plan(db, plan.id)

        with pytest.raises(RecoveryPlanExecutionConflictError) as exc_info:
            approve_recovery_plan(db, plan.id)

        assert "already been rejected" in str(exc_info.value).lower()

    def test_contradictory_rejection_of_approved_plan_prevented(self, approval_test_env):
        """Attempting to reject an already approved plan is blocked."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        with pytest.raises(RecoveryPlanExecutionConflictError) as exc_info:
            reject_recovery_plan(db, plan.id)

        assert "already been approved" in str(exc_info.value).lower()

    def test_stale_plan_approval_blocked_and_auto_rejected(self, approval_test_env):
        """
        Attempting to approve a stale plan is blocked:
        - Plan status transitions to REJECTED.
        - Rejection reason noting staleness is recorded.
        - RecoveryPlanStaleError is raised.
        """
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # Execution subsequently succeeds (state change)
        exec_record.status = ExecutionStatus.COMPLETED.value
        db.commit()

        # Approval attempt on stale plan
        with pytest.raises(RecoveryPlanStaleError) as exc_info:
            approve_recovery_plan(db, plan.id)

        assert "stale" in str(exc_info.value).lower()

        # Plan has been auto-marked REJECTED with recorded reason
        db.refresh(plan)
        assert plan.status == RecoveryPlanStatus.REJECTED.value
        assert "stale" in (plan.decision_reason or "").lower()

    def test_blocking_conflict_approval_blocked_and_auto_rejected(self, approval_test_env):
        """
        Attempting to approve a plan with a critical unresolved conflict (e.g. concurrent active plan)
        is blocked:
        - Plan status transitions to REJECTED.
        - Rejection reason noting the blocking conflict is recorded.
        - RecoveryPlanExecutionConflictError is raised.
        """
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        plan2 = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan2.id)

        # Plan 2 is actively executing
        plan2.status = RecoveryPlanStatus.EXECUTING.value
        db.commit()

        # Attempting to approve plan 1 has critical conflict
        with pytest.raises(RecoveryPlanExecutionConflictError) as exc_info:
            approve_recovery_plan(db, plan1.id)

        assert "blocking conflict" in str(exc_info.value).lower() or "critical" in str(exc_info.value).lower()

        # Plan 1 is marked REJECTED
        db.refresh(plan1)
        assert plan1.status == RecoveryPlanStatus.REJECTED.value

    def test_manual_review_unapproved_plan_cannot_execute(self, approval_test_env):
        """A plan requiring manual review cannot execute before explicit operator authorization."""
        db, create_workflow, created_executions, created_plans = approval_test_env

        wf = create_workflow(["Send SMS Notification", "Debit Ledger"])
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

        # Cannot execute unapproved plan
        with pytest.raises(RecoveryPlanNotApprovedError):
            execute_recovery_plan(db, plan.id)

        # Approval without authorize_manual_review fails
        with pytest.raises(RecoveryPlanUnauthorizedActionError):
            approve_recovery_plan(db, plan.id, RecoveryPlanApprovalRequest(authorize_manual_review=False))

        # Explicit approval succeeds and enables execution
        approve_recovery_plan(
            db,
            plan.id,
            RecoveryPlanApprovalRequest(authorize_manual_review=True, reason="SMS side effect acknowledged"),
        )
        completed = execute_recovery_plan(db, plan.id)
        assert completed.status == RecoveryPlanStatus.COMPLETED.value

    def test_original_execution_history_preserved(self, approval_test_env):
        """Approval, rejection, and decision recording must never mutate original executions."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        orig_status = exec_record.status
        orig_started = exec_record.started_at
        orig_completed = exec_record.completed_at
        orig_attempt = exec_record.attempt_number

        approve_recovery_plan(db, plan.id, RecoveryPlanApprovalRequest(reason="Approve"))
        db.refresh(exec_record)

        assert exec_record.status == orig_status == ExecutionStatus.FAILED.value
        assert exec_record.started_at == orig_started
        assert exec_record.completed_at == orig_completed
        assert exec_record.attempt_number == orig_attempt


# ---------------------------------------------------------------------------
# API TESTS: Approval and Rejection REST Endpoints
# ---------------------------------------------------------------------------
class TestOperatorApprovalRejectionAPI:
    """Tests HTTP endpoints for approving and rejecting recovery plans."""

    def test_api_approve_plan_stores_reason_and_operator(self, approval_test_env):
        """POST /recovery-plans/{id}/approve returns 200 and records decision details."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        resp = client.post(
            f"/recovery-plans/{plan.id}/approve",
            json={
                "operator": "ops_charlie",
                "reason": "Production incident reviewed; recovery authorized",
                "authorize_manual_review": False,
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["status"] == "APPROVED"
        assert data["decision_operator"] == "ops_charlie"
        assert data["decision_reason"] == "Production incident reviewed; recovery authorized"
        assert data["decided_at"] is not None

    def test_api_reject_plan_stores_reason_and_operator(self, approval_test_env):
        """POST /recovery-plans/{id}/reject returns 200 and records decision details."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        resp = client.post(
            f"/recovery-plans/{plan.id}/reject",
            json={
                "operator": "ops_diana",
                "reason": "Alternative recovery path chosen",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["status"] == "REJECTED"
        assert data["decision_operator"] == "ops_diana"
        assert data["decision_reason"] == "Alternative recovery path chosen"
        assert data["decided_at"] is not None

    def test_api_duplicate_approval_returns_409(self, approval_test_env):
        """POST /recovery-plans/{id}/approve returns 409 for duplicate approval."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # First approval -> 200
        resp1 = client.post(f"/recovery-plans/{plan.id}/approve", json={})
        assert resp1.status_code == status.HTTP_200_OK

        # Second approval -> 409 Conflict
        resp2 = client.post(f"/recovery-plans/{plan.id}/approve", json={})
        assert resp2.status_code == status.HTTP_409_CONFLICT
        assert "already been approved" in resp2.json()["detail"].lower()

    def test_api_contradictory_approval_of_rejected_plan_returns_409(self, approval_test_env):
        """POST /recovery-plans/{id}/approve returns 409 if plan was already rejected."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # Reject plan -> 200
        resp_reject = client.post(f"/recovery-plans/{plan.id}/reject", json={})
        assert resp_reject.status_code == status.HTTP_200_OK

        # Try to approve rejected plan -> 409 Conflict
        resp_approve = client.post(f"/recovery-plans/{plan.id}/approve", json={})
        assert resp_approve.status_code == status.HTTP_409_CONFLICT
        assert "already been rejected" in resp_approve.json()["detail"].lower()

    def test_api_rejected_plan_cannot_execute_returns_400(self, approval_test_env):
        """POST /recovery-plans/{id}/execute returns 400 when attempting to execute a rejected plan."""
        db, create_workflow, created_executions, created_plans = approval_test_env

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

        # Reject plan
        client.post(
            f"/recovery-plans/{plan.id}/reject",
            json={"reason": "Rejected by security policy"},
        )

        # Execute rejected plan
        resp_exec = client.post(f"/recovery-plans/{plan.id}/execute", json={})
        assert resp_exec.status_code == status.HTTP_400_BAD_REQUEST
        assert "rejected" in resp_exec.json()["detail"].lower()
