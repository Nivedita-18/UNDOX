"""
Tests for Workflow Registration and Inspection REST API endpoints and Pydantic schemas.
Covers validation rules, transactional persistence, ordering guarantees, and error handling.
"""

import uuid
from typing import Generator
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.database import SessionLocal
from backend.app.main import app
from backend.app.models.workflow import WorkflowInstance, WorkflowStatus, StepStatus
from backend.app.schemas.workflow import StepCreate, WorkflowCreate

client = TestClient(app)


# ---------------------------------------------------------------------------
# FIXTURE: Clean database session that tracks and cleans up created test rows
# ---------------------------------------------------------------------------
@pytest.fixture
def test_db() -> Generator[SessionLocal, None, None]:
    """
    Provides a real database session to test live PostgreSQL persistence.
    Tracks any WorkflowInstance IDs created during the test and deletes only
    those specific rows in teardown (cascading to steps).
    Does not drop tables or truncate foreign databases.
    """
    db = SessionLocal()
    created_workflow_ids = []

    yield db, created_workflow_ids

    # Teardown: Clean up only test-generated workflows
    try:
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
# UNIT TESTS: Schema-level validation rules
# ---------------------------------------------------------------------------
class TestWorkflowSchemaValidation:
    """
    Tests Pydantic validation rules independently of API routing.
    """

    def test_valid_workflow_schema(self):
        """A valid workflow with contiguous steps starting at 1 passes validation."""
        payload = WorkflowCreate(
            name="Valid Workflow",
            steps=[
                StepCreate(name="Step 1", step_order=1),
                StepCreate(name="Step 2", step_order=2),
                StepCreate(name="Step 3", step_order=3),
            ],
        )
        assert payload.name == "Valid Workflow"
        assert len(payload.steps) == 3

    def test_empty_workflow_name_rejected(self):
        """Blank or whitespace-only workflow name is rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="   ",
                steps=[StepCreate(name="Step 1", step_order=1)],
            )
        assert "Workflow name cannot be empty" in str(exc.value)

    def test_empty_step_name_rejected(self):
        """Blank or whitespace-only step name is rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="Workflow A",
                steps=[StepCreate(name="  ", step_order=1)],
            )
        assert "Step name cannot be empty" in str(exc.value)

    def test_empty_steps_list_rejected(self):
        """Workflow with no steps is rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(name="Workflow A", steps=[])
        assert "List should have at least 1 item" in str(exc.value)

    def test_duplicate_step_order_rejected(self):
        """Steps with identical step_order values are rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="Workflow A",
                steps=[
                    StepCreate(name="Step 1", step_order=1),
                    StepCreate(name="Step 2 duplicate", step_order=1),
                ],
            )
        assert "Duplicate step_order" in str(exc.value)

    def test_step_order_not_starting_at_one_rejected(self):
        """Step sequence starting at 2 instead of 1 is rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="Workflow A",
                steps=[
                    StepCreate(name="Step 2", step_order=2),
                    StepCreate(name="Step 3", step_order=3),
                ],
            )
        assert "Step ordering must start at 1" in str(exc.value)

    def test_step_order_with_gaps_rejected(self):
        """Step sequence with missing numbers (e.g. 1, 3) is rejected."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="Workflow A",
                steps=[
                    StepCreate(name="Step 1", step_order=1),
                    StepCreate(name="Step 3 gap", step_order=3),
                ],
            )
        assert "strict contiguous sequential order" in str(exc.value)

    def test_step_order_out_of_order_not_silently_reordered(self):
        """Steps provided out of order (e.g. 2, 1) are rejected rather than silently reordered."""
        with pytest.raises(ValidationError) as exc:
            WorkflowCreate(
                name="Workflow A",
                steps=[
                    StepCreate(name="Step 2 first", step_order=2),
                    StepCreate(name="Step 1 second", step_order=1),
                ],
            )
        assert "Step ordering must start at 1" in str(exc.value)


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: Live REST API endpoints & PostgreSQL persistence
# ---------------------------------------------------------------------------
class TestWorkflowAPI:
    """
    Tests REST API behavior against PostgreSQL undox_dev.
    """

    def test_create_workflow_success(self, test_db):
        """
        POST /workflows creates a workflow and steps in PostgreSQL,
        returning HTTP 201, generated UUIDs, and initial PENDING statuses.
        """
        _, created_ids = test_db
        payload = {
            "name": "E-Commerce Checkout Workflow",
            "steps": [
                {"name": "Verify Cart Items", "step_order": 1},
                {"name": "Authorize Payment", "step_order": 2},
                {"name": "Generate Invoice", "step_order": 3},
            ],
        }
        response = client.post("/workflows", json=payload)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        wf_id = uuid.UUID(data["id"])
        created_ids.append(wf_id)

        # Assert workflow fields
        assert data["name"] == "E-Commerce Checkout Workflow"
        assert data["status"] == WorkflowStatus.PENDING.value
        assert "created_at" in data
        assert "updated_at" in data

        # Assert steps persistence and order
        steps = data["steps"]
        assert len(steps) == 3
        assert [s["step_order"] for s in steps] == [1, 2, 3]
        assert [s["name"] for s in steps] == [
            "Verify Cart Items",
            "Authorize Payment",
            "Generate Invoice",
        ]
        assert all(s["status"] == StepStatus.PENDING.value for s in steps)
        assert all(s["workflow_id"] == str(wf_id) for s in steps)

    def test_create_workflow_validation_error_returns_422(self):
        """POST /workflows returns HTTP 422 on invalid schema (e.g. gaps in step order)."""
        invalid_payload = {
            "name": "Invalid Order Workflow",
            "steps": [
                {"name": "Step 1", "step_order": 1},
                {"name": "Step 3", "step_order": 3},
            ],
        }
        response = client.post("/workflows", json=invalid_payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_workflow_by_id_success(self, test_db):
        """GET /workflows/{id} returns the workflow and its ordered steps."""
        _, created_ids = test_db

        # Create a workflow first
        create_res = client.post(
            "/workflows",
            json={
                "name": "Query Test Workflow",
                "steps": [
                    {"name": "Step Alpha", "step_order": 1},
                    {"name": "Step Beta", "step_order": 2},
                ],
            },
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        wf_id = create_res.json()["id"]
        created_ids.append(uuid.UUID(wf_id))

        # Query by ID
        get_res = client.get(f"/workflows/{wf_id}")
        assert get_res.status_code == status.HTTP_200_OK
        data = get_res.json()
        assert data["id"] == wf_id
        assert data["name"] == "Query Test Workflow"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_order"] == 1
        assert data["steps"][1]["step_order"] == 2

    def test_get_workflow_not_found_returns_404(self):
        """GET /workflows/{id} with a non-existent UUID returns HTTP 404."""
        non_existent_id = uuid.uuid4()
        response = client.get(f"/workflows/{non_existent_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert f"Workflow with ID '{non_existent_id}' not found" in response.json()["detail"]

    def test_get_workflow_invalid_uuid_returns_422(self):
        """GET /workflows/{id} with an invalid UUID string is rejected by FastAPI with 422."""
        response = client.get("/workflows/not-a-valid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_workflows_pagination_and_ordering(self, test_db):
        """GET /workflows returns recent workflows ordered newest first with bounds."""
        _, created_ids = test_db

        # Create two workflows
        res1 = client.post(
            "/workflows",
            json={"name": "First WF", "steps": [{"name": "Step", "step_order": 1}]},
        )
        res2 = client.post(
            "/workflows",
            json={"name": "Second WF", "steps": [{"name": "Step", "step_order": 1}]},
        )
        created_ids.append(uuid.UUID(res1.json()["id"]))
        created_ids.append(uuid.UUID(res2.json()["id"]))

        # Query list
        list_res = client.get("/workflows?limit=10")
        assert list_res.status_code == status.HTTP_200_OK
        body = list_res.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 2

        # Verify newest is first
        item_ids = [item["id"] for item in body["items"]]
        second_idx = item_ids.index(res2.json()["id"])
        first_idx = item_ids.index(res1.json()["id"])
        assert second_idx < first_idx, "Newer workflow should appear before older workflow"

    def test_list_workflows_invalid_limit_rejected(self):
        """GET /workflows with limit=0 or limit=101 returns HTTP 422."""
        res_zero = client.get("/workflows?limit=0")
        assert res_zero.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        res_over = client.get("/workflows?limit=101")
        assert res_over.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
