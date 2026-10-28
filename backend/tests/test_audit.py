"""
Tests for Audit History and Activity Logging in UNDOX.

Covers:
- Event creation across workflow execution and recovery lifecycles:
  - Workflow execution start, completion, failure
  - Recovery plan creation
  - Recovery plan approval and rejection (including auto-rejection on staleness/conflicts)
  - Recovery execution start, completion, and failure
- Sensitive data sanitization (passwords, tokens, API keys, credentials redacted)
- History preservation when recovery operations fail (immutable, append-only logs)
- Separation of audit history from mutable execution state
- Query filtering by execution ID, recovery-plan ID, event type, and outcome
- Pagination controls (limit and offset)
- Error handling for invalid and nonexistent resource IDs
- API integration tests:
  - GET /api/v1/audit-events
  - GET /api/v1/audit-events/{event_id}
  - GET /api/v1/executions/{execution_id}/audit-events
  - GET /api/v1/recovery-plans/{plan_id}/audit-events
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

from backend.app.audit.sanitizer import sanitize_details, sanitize_text
from backend.app.audit.service import (
    AuditEventNotFoundError,
    ExecutionNotFoundError,
    RecoveryPlanNotFoundError,
    get_audit_event_by_id,
    query_audit_events,
    record_audit_event,
)
from backend.app.database import Base, get_db
from backend.app.executions.service import execute_workflow
from backend.app.main import app
from backend.app.models.audit import AuditEvent, AuditEventType, AuditOutcome
from backend.app.models.execution import (
    ExecutionStatus,
    ExecutionStep,
    WorkflowExecution,
)
from backend.app.models.recovery import (
    RecoveryActionStatus,
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
    RecoveryPlanStaleError,
    generate_recovery_plan,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig
from backend.app.schemas.recovery import (
    RecoveryExecutionRequest,
    RecoveryPlanApprovalRequest,
    RecoveryPlanRejectionRequest,
)

# ---------------------------------------------------------------------------
# In-memory SQLite Database Setup
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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def audit_test_env() -> Generator[tuple, None, None]:
    """
    Sets up an isolated database session and cleanup tracker for test entities.
    """
    db = TestingSessionLocal()
    created_workflows: List[uuid.UUID] = []
    created_executions: List[uuid.UUID] = []
    created_plans: List[uuid.UUID] = []

    def create_workflow(step_names: List[str]) -> WorkflowInstance:
        wf = WorkflowInstance(
            name=f"Workflow-{uuid.uuid4().hex[:6]}",
            status=WorkflowStatus.PENDING.value,
        )
        db.add(wf)
        db.flush()
        created_workflows.append(wf.id)

        for idx, name in enumerate(step_names, start=1):
            step = WorkflowStep(
                workflow_id=wf.id,
                step_order=idx,
                name=name,
                status=StepStatus.PENDING.value,
            )
            db.add(step)

        db.commit()
        db.refresh(wf)
        return wf

    try:
        yield db, create_workflow, created_executions, created_plans
    finally:
        # Clean up audit events first, then plans, executions, workflows
        for ev in db.execute(select(AuditEvent)).scalars().all():
            db.delete(ev)
        for plan_id in created_plans:
            p = db.get(RecoveryPlan, plan_id)
            if p:
                db.delete(p)
        for exec_id in created_executions:
            e = db.get(WorkflowExecution, exec_id)
            if e:
                db.delete(e)
        for wf_id in created_workflows:
            w = db.get(WorkflowInstance, wf_id)
            if w:
                db.delete(w)
        db.commit()
        db.close()


# ===========================================================================
# 1. Sanitization Unit Tests
# ===========================================================================

class TestAuditSanitization:
    """Validates that credentials, tokens, and secrets are strictly redacted."""

    def test_sanitize_sensitive_dictionary_keys(self):
        payload = {
            "username": "operator1",
            "password": "supersecretpassword123",
            "api_key": "key-9988776655",
            "access_token": "token-112233",
            "private_key": "private_val",
            "nested": {
                "auth_token": "bearer-xyz",
                "normal_field": "public_data",
            },
        }
        sanitized = sanitize_details(payload)
        assert sanitized["username"] == "operator1"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["access_token"] == "[REDACTED]"
        assert sanitized["private_key"] == "[REDACTED]"
        assert sanitized["nested"]["auth_token"] == "[REDACTED]"
        assert sanitized["nested"]["normal_field"] == "public_data"

    def test_sanitize_bearer_tokens_in_text(self):
        msg = "Authentication failed for header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz123"
        cleaned = sanitize_text(msg)
        assert "Bearer [REDACTED]" in cleaned
        assert "eyJhbGci" not in cleaned

    def test_sanitize_key_value_secrets_in_text(self):
        msg = "Connection error with config password=myDbPassword! and client_secret='secret999'"
        cleaned = sanitize_text(msg)
        assert "password=[REDACTED]" in cleaned
        assert "client_secret='[REDACTED]'" in cleaned
        assert "myDbPassword!" not in cleaned

    def test_sanitize_private_key_block(self):
        raw = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        cleaned = sanitize_text(raw)
        assert cleaned == "[REDACTED_PRIVATE_KEY]"


# ===========================================================================
# 2. Lifecycle Audit Recording Tests
# ===========================================================================

class TestAuditLifecycleRecording:
    """Validates audit event creation across workflow and recovery lifecycles."""

    def test_workflow_execution_records_audit_events(self, audit_test_env):
        """Starting and finishing a workflow creates WORKFLOW_EXECUTION_STARTED and COMPLETED events."""
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["Step 1", "Step 2"])

        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        # Retrieve audit events for this execution
        events, total = query_audit_events(db, execution_id=exec_record.id)
        assert total >= 2

        event_types = [e.event_type for e in events]
        assert AuditEventType.WORKFLOW_EXECUTION_STARTED.value in event_types
        assert AuditEventType.WORKFLOW_EXECUTION_COMPLETED.value in event_types

        # Verify details
        completed_event = next(e for e in events if e.event_type == AuditEventType.WORKFLOW_EXECUTION_COMPLETED.value)
        assert completed_event.outcome == AuditOutcome.SUCCESS.value
        assert completed_event.execution_id == exec_record.id

    def test_workflow_failure_records_audit_events(self, audit_test_env):
        """Failed execution creates WORKFLOW_EXECUTION_STARTED and WORKFLOW_EXECUTION_FAILED events."""
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["Validate Order", "Charge Card"])

        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(
                    fail_at_step_order=2,
                    error_message="Card declined (token=secretToken123)",
                )
            ),
        )
        created_executions.append(exec_record.id)

        events, total = query_audit_events(db, execution_id=exec_record.id)
        failed_event = next(e for e in events if e.event_type == AuditEventType.WORKFLOW_EXECUTION_FAILED.value)

        assert failed_event.outcome == AuditOutcome.FAILED.value
        assert "Card declined" in failed_event.message
        # Verify secret token in message was sanitized
        assert "secretToken123" not in failed_event.message
        assert "[REDACTED]" in failed_event.message

    def test_recovery_plan_creation_records_audit_event(self, audit_test_env):
        """Generating a recovery plan records RECOVERY_PLAN_CREATED."""
        db, create_workflow, created_executions, created_plans = audit_test_env
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

        events, total = query_audit_events(db, recovery_plan_id=plan.id)
        assert total >= 1

        created_event = next(e for e in events if e.event_type == AuditEventType.RECOVERY_PLAN_CREATED.value)
        assert created_event.outcome == AuditOutcome.SUCCESS.value
        assert created_event.recovery_plan_id == plan.id
        assert created_event.execution_id == exec_record.id
        assert "actions" in created_event.message

    def test_recovery_plan_approval_and_rejection_record_audit_events(self, audit_test_env):
        """Operator approval and rejection explicitly record audit events."""
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(fail_at_step_order=2)
            ),
        )
        created_executions.append(exec_record.id)

        # Plan 1: Approved
        plan1 = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan1.id)

        approve_recovery_plan(
            db,
            plan1.id,
            RecoveryPlanApprovalRequest(
                operator="operator_alice",
                reason="Plan verified safe for execution",
            ),
        )

        events1, _ = query_audit_events(db, recovery_plan_id=plan1.id)
        approved_event = next(e for e in events1 if e.event_type == AuditEventType.RECOVERY_PLAN_APPROVED.value)
        assert approved_event.outcome == AuditOutcome.APPROVED.value
        assert approved_event.actor == "operator_alice"
        assert "Plan verified safe" in approved_event.message

        # Plan 2: Rejected
        plan2 = generate_recovery_plan(db, exec_record.id)
        created_plans.append(plan2.id)

        reject_recovery_plan(
            db,
            plan2.id,
            RecoveryPlanRejectionRequest(
                operator="operator_bob",
                reason="Not suitable for automatic execution",
            ),
        )

        events2, _ = query_audit_events(db, recovery_plan_id=plan2.id)
        rejected_event = next(e for e in events2 if e.event_type == AuditEventType.RECOVERY_PLAN_REJECTED.value)
        assert rejected_event.outcome == AuditOutcome.REJECTED.value
        assert rejected_event.actor == "operator_bob"
        assert "Not suitable" in rejected_event.message

    def test_recovery_execution_records_audit_events(self, audit_test_env):
        """Recovery plan execution records RECOVERY_EXECUTION_STARTED and COMPLETED."""
        db, create_workflow, created_executions, created_plans = audit_test_env
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

        events, _ = query_audit_events(db, recovery_plan_id=plan.id)
        types = [e.event_type for e in events]
        assert AuditEventType.RECOVERY_EXECUTION_STARTED.value in types
        assert AuditEventType.RECOVERY_EXECUTION_COMPLETED.value in types


# ===========================================================================
# 3. History Preservation & Failure Resilience Tests
# ===========================================================================

class TestAuditHistoryPreservation:
    """Validates that history is strictly preserved when a recovery operation fails."""

    def test_history_preserved_when_recovery_operation_fails(self, audit_test_env):
        """
        When simulated action failure halts recovery execution:
        - Prior events (PLAN_CREATED, PLAN_APPROVED, EXECUTION_STARTED) remain intact.
        - RECOVERY_EXECUTION_FAILED is appended.
        - Historical order is preserved.
        """
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["Debit Account", "Ship Item", "Notify Customer"])
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

        approve_recovery_plan(
            db,
            plan.id,
            RecoveryPlanApprovalRequest(
                operator="lead_operator",
                authorize_manual_review=True,
                reason="Approved for controlled rollback",
            ),
        )

        # Execute with injected failure at action order 1
        executed_plan = execute_recovery_plan(
            db,
            plan.id,
            RecoveryExecutionRequest(
                simulate_action_failure_at_order=1,
                simulated_error_message="Simulated connection timeout during compensation",
            ),
        )
        assert executed_plan.status == RecoveryPlanStatus.FAILED.value

        # Retrieve all events for this recovery plan
        events, total = query_audit_events(db, recovery_plan_id=plan.id)
        assert total >= 4

        event_types = [e.event_type for e in events]
        # Chronological descending order check
        assert event_types[0] == AuditEventType.RECOVERY_EXECUTION_FAILED.value
        assert AuditEventType.RECOVERY_EXECUTION_STARTED.value in event_types
        assert AuditEventType.RECOVERY_PLAN_APPROVED.value in event_types
        assert AuditEventType.RECOVERY_PLAN_CREATED.value in event_types

        failed_event = next(e for e in events if e.event_type == AuditEventType.RECOVERY_EXECUTION_FAILED.value)
        assert failed_event.outcome == AuditOutcome.FAILED.value
        assert "Simulated connection timeout" in failed_event.message

    def test_auto_rejected_stale_plan_preserves_audit_event(self, audit_test_env):
        """When approval is rejected due to staleness, RECOVERY_PLAN_REJECTED is recorded."""
        db, create_workflow, created_executions, created_plans = audit_test_env
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

        # Mutate execution status to COMPLETED
        exec_record.status = ExecutionStatus.COMPLETED.value
        db.commit()

        # Approval fails with staleness error
        with pytest.raises(RecoveryPlanStaleError):
            approve_recovery_plan(db, plan.id)

        events, _ = query_audit_events(db, recovery_plan_id=plan.id)
        types = [e.event_type for e in events]
        assert AuditEventType.RECOVERY_PLAN_CREATED.value in types
        assert AuditEventType.RECOVERY_PLAN_REJECTED.value in types

        rejection_event = next(e for e in events if e.event_type == AuditEventType.RECOVERY_PLAN_REJECTED.value)
        assert rejection_event.outcome == AuditOutcome.REJECTED.value
        assert "stale" in rejection_event.message.lower()


# ===========================================================================
# 4. Service Filtering and Pagination Tests
# ===========================================================================

class TestAuditFilteringAndPagination:
    """Validates filtering and pagination across audit event queries."""

    def test_filter_by_event_type_and_outcome(self, audit_test_env):
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["A", "B"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        # Filter by event_type
        started_events, count = query_audit_events(
            db,
            execution_id=exec_record.id,
            event_type=AuditEventType.WORKFLOW_EXECUTION_STARTED.value,
        )
        assert count == 1
        assert started_events[0].event_type == AuditEventType.WORKFLOW_EXECUTION_STARTED.value

        # Filter by outcome
        success_events, count = query_audit_events(
            db,
            execution_id=exec_record.id,
            outcome=AuditOutcome.SUCCESS.value,
        )
        assert count == 1
        assert success_events[0].outcome == AuditOutcome.SUCCESS.value

    def test_pagination_limit_and_offset(self, audit_test_env):
        db, create_workflow, created_executions, created_plans = audit_test_env
        wf = create_workflow(["Step 1", "Step 2", "Step 3"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        # Create multiple manual events to test pagination
        for i in range(5):
            record_audit_event(
                db=db,
                event_type="CUSTOM_TEST_EVENT",
                outcome=AuditOutcome.INFO.value,
                message=f"Pagination test event {i}",
                execution_id=exec_record.id,
            )

        page1, total = query_audit_events(db, execution_id=exec_record.id, limit=3, offset=0)
        assert len(page1) == 3
        assert total >= 7

        page2, _ = query_audit_events(db, execution_id=exec_record.id, limit=3, offset=3)
        assert len(page2) == 3
        assert page1[0].id != page2[0].id

    def test_filter_nonexistent_execution_raises_error(self, audit_test_env):
        db, _, _, _ = audit_test_env
        missing_id = uuid.uuid4()
        with pytest.raises(ExecutionNotFoundError):
            query_audit_events(db, execution_id=missing_id)

    def test_filter_nonexistent_recovery_plan_raises_error(self, audit_test_env):
        db, _, _, _ = audit_test_env
        missing_id = uuid.uuid4()
        with pytest.raises(RecoveryPlanNotFoundError):
            query_audit_events(db, recovery_plan_id=missing_id)


# ===========================================================================
# 5. REST API Integration Tests
# ===========================================================================

class TestAuditAPI:
    """Validates the audit history REST API endpoints."""

    def test_api_list_audit_events_pagination(self, client, audit_test_env):
        db, create_workflow, created_executions, _ = audit_test_env
        wf = create_workflow(["Alpha", "Beta"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        response = client.get("/api/v1/audit-events?limit=10&offset=0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["total"] >= 2

    def test_api_filter_by_execution_id(self, client, audit_test_env):
        db, create_workflow, created_executions, _ = audit_test_env
        wf = create_workflow(["Alpha", "Beta"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        response = client.get(f"/api/v1/audit-events?execution_id={exec_record.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            assert item["execution_id"] == str(exec_record.id)

    def test_api_filter_by_recovery_plan_id(self, client, audit_test_env):
        db, create_workflow, created_executions, created_plans = audit_test_env
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

        response = client.get(f"/api/v1/audit-events?recovery_plan_id={plan.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) >= 1
        assert data["items"][0]["recovery_plan_id"] == str(plan.id)

    def test_api_get_audit_event_by_id(self, client, audit_test_env):
        db, create_workflow, created_executions, _ = audit_test_env
        wf = create_workflow(["Step 1"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        events, _ = query_audit_events(db, execution_id=exec_record.id)
        event_id = events[0].id

        response = client.get(f"/api/v1/audit-events/{event_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(event_id)
        assert data["event_type"] == events[0].event_type

    def test_api_get_nonexistent_audit_event_returns_404(self, client):
        missing_id = uuid.uuid4()
        response = client.get(f"/api/v1/audit-events/{missing_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"'{missing_id}' not found" in response.json()["detail"]

    def test_api_filter_nonexistent_execution_returns_404(self, client):
        missing_id = uuid.uuid4()
        response = client.get(f"/api/v1/audit-events?execution_id={missing_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"Execution with ID '{missing_id}' not found" in response.json()["detail"]

    def test_api_filter_nonexistent_plan_returns_404(self, client):
        missing_id = uuid.uuid4()
        response = client.get(f"/api/v1/audit-events?recovery_plan_id={missing_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"Recovery plan with ID '{missing_id}' not found" in response.json()["detail"]

    def test_api_execution_subresource_endpoint(self, client, audit_test_env):
        db, create_workflow, created_executions, _ = audit_test_env
        wf = create_workflow(["Step 1", "Step 2"])
        exec_record = execute_workflow(db, wf.id, ExecutionRequest())
        created_executions.append(exec_record.id)

        response = client.get(f"/api/v1/executions/{exec_record.id}/audit-events")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["execution_id"] == str(exec_record.id)

    def test_api_recovery_plan_subresource_endpoint(self, client, audit_test_env):
        db, create_workflow, created_executions, created_plans = audit_test_env
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

        response = client.get(f"/api/v1/recovery-plans/{plan.id}/audit-events")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["recovery_plan_id"] == str(plan.id)

    def test_api_invalid_uuid_returns_422(self, client):
        response = client.get("/api/v1/audit-events/invalid-uuid-string")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_api_invalid_pagination_limit_returns_422(self, client):
        response = client.get("/api/v1/audit-events?limit=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
