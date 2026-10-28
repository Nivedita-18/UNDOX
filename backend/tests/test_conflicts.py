"""
Tests for the Conflict Detection Engine in UNDOX.

Covers:
- Schema validation for ConflictDetail and RecoveryPlanConflictReport.
- Conflict Detection Service:
  - Clean plans without conflicts.
  - Stale plans:
    - Execution status transitioned from FAILED to another state.
    - Execution superseded by a newer execution attempt.
    - Parent workflow status in active/terminal incompatible state.
    - Execution step status mismatch against planned recovery action.
    - Superseded by a newer recovery plan.
  - Conflicting recovery actions:
    - Multiple duplicate actions targeting the same step.
    - Contradictory action types targeting the same step.
    - Saga reverse-order (LIFO) compensation ordering violations.
  - Irreversible actions and manual review requirement detection.
  - Concurrent active recovery plans (EXECUTING or APPROVED).
  - Error handling for nonexistent plans (RecoveryPlanNotFoundError).
  - Read-only integrity: zero mutation to execution or plan state.
- Conflict REST API:
  - GET /recovery-plans/{id}/conflicts (200 OK for clean and conflicted plans).
  - GET /recovery-plans/{id}/conflicts (404 Not Found for missing plan).
  - GET /recovery-plans/{invalid-uuid}/conflicts (422 Unprocessable Content).
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
from backend.app.recovery.conflicts import detect_recovery_conflicts
from backend.app.recovery.service import (
    RecoveryPlanNotFoundError,
    generate_recovery_plan,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig
from backend.app.schemas.recovery import (
    ConflictDetail,
    ConflictSeverity,
    ConflictType,
    RecoveryPlanConflictReport,
    RecoveryPlanRequest,
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
def conflict_test_env() -> Generator:
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
            name="Conflict Test Workflow",
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
# UNIT TESTS: Conflict Detection Engine Schemas
# ---------------------------------------------------------------------------
class TestConflictSchemas:
    """Validates schemas and enums used by the Conflict Detection Engine."""

    def test_conflict_severity_values(self):
        assert ConflictSeverity.CRITICAL.value == "CRITICAL"
        assert ConflictSeverity.HIGH.value == "HIGH"
        assert ConflictSeverity.MEDIUM.value == "MEDIUM"
        assert ConflictSeverity.LOW.value == "LOW"

    def test_conflict_report_schema_instantiation(self):
        report = RecoveryPlanConflictReport(
            plan_id=uuid.uuid4(),
            execution_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            has_conflicts=False,
            is_stale=False,
            requires_manual_approval=False,
            conflict_count=0,
            highest_severity=None,
            conflicts=[],
        )
        assert report.has_conflicts is False
        assert report.is_stale is False
        assert report.conflict_count == 0
        assert report.highest_severity is None


# ---------------------------------------------------------------------------
# UNIT TESTS: Conflict Detection Engine Core Logic
# ---------------------------------------------------------------------------
class TestConflictDetectionService:
    """Tests analytical conflict detection on recovery plans."""

    def test_plan_without_conflicts(self, conflict_test_env):
        """
        A standard plan generated for a failed execution with safe reversible steps
        should have zero conflicts, is_stale=False, and highest_severity=None.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Reserve Seats", "Debit Card", "Print Boarding Pass"])
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

        report = detect_recovery_conflicts(db, plan.id)

        assert report.plan_id == plan.id
        assert report.execution_id == exec_record.id
        assert report.workflow_id == wf.id
        assert report.has_conflicts is False
        assert report.is_stale is False
        assert report.requires_manual_approval is False
        assert report.conflict_count == 0
        assert report.highest_severity is None
        assert report.conflicts == []

    def test_stale_plan_execution_status_transitioned(self, conflict_test_env):
        """
        When the execution status changes from FAILED to COMPLETED or RUNNING,
        the recovery plan must be flagged as stale with CRITICAL severity.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        # Execution subsequently transitions to COMPLETED
        exec_record.status = ExecutionStatus.COMPLETED.value
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.is_stale is True
        assert report.highest_severity == ConflictSeverity.CRITICAL.value
        assert any(
            c.conflict_type == ConflictType.STALE_PLAN_EXECUTION_STATUS_CHANGED.value
            for c in report.conflicts
        )

    def test_stale_plan_superseded_by_newer_execution_attempt(self, conflict_test_env):
        """
        When a new execution attempt is triggered for the workflow, the previous
        plan becomes stale with CRITICAL severity.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Step 1", "Step 2"])
        # Attempt 1 fails
        exec1 = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec1.id)

        plan = generate_recovery_plan(db, exec1.id)
        created_plans.append(plan.id)

        # Attempt 2 is subsequently launched
        exec2 = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec2.id)

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.is_stale is True
        assert report.highest_severity == ConflictSeverity.CRITICAL.value
        assert any(
            c.conflict_type == ConflictType.STALE_PLAN_SUPERSEDED_EXECUTION.value
            for c in report.conflicts
        )

    def test_stale_plan_incompatible_workflow_status(self, conflict_test_env):
        """
        When the parent workflow status is COMPLETED or RECOVERED, the plan is flagged stale.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        # Set workflow status to RECOVERED
        wf.status = WorkflowStatus.RECOVERED.value
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.is_stale is True
        assert any(
            c.conflict_type == ConflictType.STALE_PLAN_WORKFLOW_STATE_INCOMPATIBLE.value
            for c in report.conflicts
        )

    def test_stale_step_state_mismatch(self, conflict_test_env):
        """
        If a completed step is altered or fails after plan generation, a step status
        mismatch conflict is detected.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        # Mutate step 1 status from COMPLETED to FAILED
        step1 = [s for s in exec_record.execution_steps if s.step_order == 1][0]
        step1.status = ExecutionStepStatus.FAILED.value
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.is_stale is True
        assert any(
            c.conflict_type == ConflictType.STALE_STEP_STATE_MISMATCH.value
            for c in report.conflicts
        )

    def test_conflicting_actions_duplicate_target_step(self, conflict_test_env):
        """
        Detects duplicate recovery actions targeting the same step within a plan.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        # Inject an additional duplicate COMPENSATE action on step 1
        dup_action = RecoveryPlanAction(
            plan_id=plan.id,
            action_order=99,
            target_step_order=1,
            action_type=RecoveryActionType.COMPENSATE.value,
            target_step_name="Step 1",
            status=RecoveryActionStatus.PROPOSED.value,
            is_reversible=True,
            explanation="Duplicate simulated reversal",
        )
        db.add(dup_action)
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.highest_severity == ConflictSeverity.HIGH.value
        assert any(
            c.conflict_type == ConflictType.DUPLICATE_ACTION.value
            for c in report.conflicts
        )

    def test_conflicting_actions_contradictory_types(self, conflict_test_env):
        """
        Detects contradictory recovery actions (e.g. COMPENSATE and RETRY) targeting the same step.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        # Inject a RETRY action for step 1 which already has a COMPENSATE action
        contradictory_action = RecoveryPlanAction(
            plan_id=plan.id,
            action_order=99,
            target_step_order=1,
            action_type=RecoveryActionType.RETRY.value,
            target_step_name="Step 1",
            status=RecoveryActionStatus.PROPOSED.value,
            is_reversible=True,
            explanation="Contradictory retry",
        )
        db.add(contradictory_action)
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.highest_severity == ConflictSeverity.HIGH.value
        assert any(
            c.conflict_type == ConflictType.CONTRADICTORY_ACTIONS.value
            for c in report.conflicts
        )

    def test_ordering_conflict_violating_lifo(self, conflict_test_env):
        """
        Detects ordering conflicts when compensation actions are not in reverse (LIFO) order.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Step 1", "Step 2", "Step 3"])
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

        # Normally actions are: Action 1 -> Step 2, Action 2 -> Step 1
        # Invert target_step_orders to violate LIFO
        actions = sorted(plan.actions, key=lambda a: a.action_order)
        actions[0].target_step_order = 1
        actions[1].target_step_order = 2
        db.commit()

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.highest_severity == ConflictSeverity.HIGH.value
        assert any(
            c.conflict_type == ConflictType.ORDERING_CONFLICT.value
            for c in report.conflicts
        )

    def test_irreversible_actions_and_manual_review_flagged(self, conflict_test_env):
        """
        Actions that are irreversible (or require manual review) must be flagged with MEDIUM severity.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Send Email Notification", "Process Charge"])
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

        report = detect_recovery_conflicts(db, plan.id)

        assert report.has_conflicts is True
        assert report.requires_manual_approval is True
        assert report.highest_severity == ConflictSeverity.MEDIUM.value
        assert any(
            c.conflict_type == ConflictType.IRREVERSIBLE_ACTION.value
            for c in report.conflicts
        )
        assert any(
            c.conflict_type == ConflictType.MANUAL_APPROVAL_REQUIRED.value
            for c in report.conflicts
        )

    def test_concurrent_active_plan_conflict(self, conflict_test_env):
        """
        If another recovery plan for the same execution is actively EXECUTING or APPROVED,
        a concurrency conflict with CRITICAL severity must be reported.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

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
            RecoveryPlanRequest(strategy="RETRY_ONLY"),
        )
        created_plans.append(plan2.id)

        # Mark plan2 as EXECUTING
        plan2.status = RecoveryPlanStatus.EXECUTING.value
        db.commit()

        # Check conflicts on plan1
        report = detect_recovery_conflicts(db, plan1.id)

        assert report.has_conflicts is True
        assert report.highest_severity == ConflictSeverity.CRITICAL.value
        assert any(
            c.conflict_type == ConflictType.ACTIVE_PLAN_CONCURRENCY.value
            for c in report.conflicts
        )

    def test_missing_plan_raises_not_found(self, conflict_test_env):
        """Calling detect_recovery_conflicts with a nonexistent UUID raises RecoveryPlanNotFoundError."""
        db, _, _, _ = conflict_test_env
        missing_id = uuid.uuid4()

        with pytest.raises(RecoveryPlanNotFoundError) as exc_info:
            detect_recovery_conflicts(db, missing_id)

        assert str(missing_id) in str(exc_info.value)

    def test_read_only_integrity_preserved(self, conflict_test_env):
        """
        Conflict detection must be strictly read-only: zero mutations to executions,
        steps, plans, or actions.
        """
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Step A", "Step B"])
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

        orig_plan_status = plan.status
        orig_exec_status = exec_record.status
        orig_attempt_number = exec_record.attempt_number

        report = detect_recovery_conflicts(db, plan.id)
        assert report is not None

        db.refresh(plan)
        db.refresh(exec_record)

        assert plan.status == orig_plan_status
        assert exec_record.status == orig_exec_status
        assert exec_record.attempt_number == orig_attempt_number


# ---------------------------------------------------------------------------
# API TESTS: GET /recovery-plans/{id}/conflicts
# ---------------------------------------------------------------------------
class TestConflictAPI:
    """Tests the conflict inspection REST endpoint."""

    def test_inspect_conflicts_clean_plan_api(self, conflict_test_env):
        """GET /recovery-plans/{id}/conflicts returns 200 with clean report."""
        db, create_workflow, created_executions, created_plans = conflict_test_env

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

        resp = client.get(f"/recovery-plans/{plan.id}/conflicts")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["plan_id"] == str(plan.id)
        assert data["has_conflicts"] is False
        assert data["is_stale"] is False
        assert data["conflict_count"] == 0
        assert data["highest_severity"] is None
        assert data["conflicts"] == []

    def test_inspect_conflicts_conflicted_plan_api(self, conflict_test_env):
        """GET /recovery-plans/{id}/conflicts returns 200 with detected conflict details."""
        db, create_workflow, created_executions, created_plans = conflict_test_env

        wf = create_workflow(["Send Customer Notification", "Process Payment"])
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

        resp = client.get(f"/recovery-plans/{plan.id}/conflicts")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["has_conflicts"] is True
        assert data["conflict_count"] > 0
        assert data["highest_severity"] == "MEDIUM"
        assert len(data["conflicts"]) > 0

    def test_inspect_conflicts_not_found_api(self):
        """GET /recovery-plans/{id}/conflicts returns 404 for nonexistent plan ID."""
        missing_id = uuid.uuid4()
        resp = client.get(f"/recovery-plans/{missing_id}/conflicts")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in resp.json()["detail"].lower()

    def test_inspect_conflicts_invalid_uuid_api(self):
        """GET /recovery-plans/{invalid-uuid}/conflicts returns 422."""
        resp = client.get("/recovery-plans/not-a-valid-uuid/conflicts")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
