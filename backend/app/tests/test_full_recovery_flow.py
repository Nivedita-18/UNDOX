import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.database import SessionLocal
from app.models import User

client = TestClient(app)

def create_authenticated_user(role="OPERATOR"):
    email = f"user_{role.lower()}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    # Register
    reg = client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text

    # Update role if needed
    if role != "VIEWER":
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            user.role = role
            db.commit()

    # Login
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, email


def test_full_demonstration_journey():
    """
    Verifies the end-to-end journey required:
    Register → Login → Create Workflow → Execute Workflow → Simulate Failure →
    Generate Recovery Plan → Detect Conflicts → Preview Recovery →
    Approve Recovery → Execute Recovery → Verify Result → View Audit History.
    """
    # 1. Register & Login as Operator
    headers, email = create_authenticated_user(role="OPERATOR")

    # 2. Create Workflow with ordered steps, input payload and compensation payload
    workflow_payload = {
        "name": f"E-Commerce Order Fulfillment {uuid.uuid4().hex[:6]}",
        "description": "Order validation, payment capture, inventory reservation, and dispatch",
        "steps": [
            {
                "name": "Validate Order",
                "step_order": 1,
                "payload": {"order_id": "ORD-9982", "channel": "web"},
                "compensation_payload": None,
                "is_reversible": False
            },
            {
                "name": "Process Payment",
                "step_order": 2,
                "payload": {"amount": 250.0, "currency": "USD", "method": "credit_card"},
                "compensation_payload": {
                    "action": "refund_payment",
                    "amount": 250.0,
                    "currency": "USD",
                    "gateway": "stripe_sim"
                },
                "is_reversible": True
            },
            {
                "name": "Reserve Inventory",
                "step_order": 3,
                "payload": {"sku": "LAPTOP-M3", "quantity": 1},
                "compensation_payload": {
                    "action": "release_stock",
                    "sku": "LAPTOP-M3",
                    "quantity": 1
                },
                "is_reversible": True
            },
            {
                "name": "Dispatch Shipment",
                "step_order": 4,
                "payload": {"carrier": "FedEx", "service": "Overnight"},
                "compensation_payload": None,
                "is_reversible": False
            }
        ]
    }

    create_wf_res = client.post("/workflows", json=workflow_payload, headers=headers)
    assert create_wf_res.status_code == 201, create_wf_res.text
    wf_data = create_wf_res.json()
    workflow_id = wf_data["id"]
    assert len(wf_data["steps"]) == 4

    # 3. Execute Workflow with simulated failure on step 4 (Dispatch Shipment)
    exec_res = client.post(
        f"/workflows/{workflow_id}/execute",
        json={
            "simulate_failure": True,
            "failure_step_order": 4,
            "failure_message": "Courier API unavailable: Dispatch timeout"
        },
        headers=headers
    )
    assert exec_res.status_code == 201, exec_res.text
    exec_data = exec_res.json()
    execution_id = exec_data["id"]
    assert exec_data["status"] == "FAILED"
    assert exec_data["error_message"] == "Courier API unavailable: Dispatch timeout"

    # Verify execution steps statuses
    steps_by_order = {s["step_order"]: s for s in exec_data["steps"]}
    assert steps_by_order[1]["status"] == "COMPLETED"
    assert steps_by_order[2]["status"] == "COMPLETED"
    assert steps_by_order[3]["status"] == "COMPLETED"
    assert steps_by_order[4]["status"] == "FAILED"

    # 4. Generate Recovery Plan
    plan_res = client.post(
        f"/executions/{execution_id}/recovery-plans",
        headers=headers
    )
    assert plan_res.status_code == 201, plan_res.text
    plan_data = plan_res.json()
    plan_id = plan_data["id"]
    assert plan_data["status"] == "GENERATED"
    actions = plan_data["actions"]
    assert len(actions) == 4

    # Verification of reversed action sequence
    actions_by_order = {a["action_order"]: a for a in actions}
    # Step 4 (FAILED) -> RETRY (action_order 1)
    assert actions_by_order[1]["action_type"] == "RETRY"
    # Step 3 (COMPLETED, reversible) -> COMPENSATE (action_order 2)
    assert actions_by_order[2]["action_type"] == "COMPENSATE"
    assert actions_by_order[2]["payload"]["action"] == "release_stock"
    # Step 2 (COMPLETED, reversible) -> COMPENSATE (action_order 3)
    assert actions_by_order[3]["action_type"] == "COMPENSATE"
    assert actions_by_order[3]["payload"]["action"] == "refund_payment"
    # Step 1 (COMPLETED, not reversible) -> MANUAL_REVIEW (action_order 4)
    assert actions_by_order[4]["action_type"] == "MANUAL_REVIEW"

    # 5. Detect Conflicts
    conflicts_res = client.get(
        f"/recovery-plans/{plan_id}/conflicts",
        headers=headers
    )
    assert conflicts_res.status_code == 200, conflicts_res.text
    conflicts_data = conflicts_res.json()
    assert conflicts_data["conflict_count"] == 0
    assert len(conflicts_data["manual_review_required"]) > 0

    # 6. Preview Recovery Plan
    preview_res = client.get(
        f"/recovery-plans/{plan_id}",
        headers=headers
    )
    assert preview_res.status_code == 200, preview_res.text
    assert preview_res.json()["id"] == plan_id

    # 7. Approve Recovery Plan
    # Attempting to approve without acknowledging manual review should fail with 422
    unack_res = client.post(
        f"/recovery-plans/{plan_id}/approve",
        json={"reason": "Approved", "manual_review_acknowledged": False},
        headers=headers
    )
    assert unack_res.status_code == 422

    # Acknowledge and approve
    approve_res = client.post(
        f"/recovery-plans/{plan_id}/approve",
        json={
            "reason": "All compensation actions and manual steps verified by operator.",
            "manual_review_acknowledged": True
        },
        headers=headers
    )
    assert approve_res.status_code == 200, approve_res.text
    assert approve_res.json()["status"] == "APPROVED"

    # 8. Execute Recovery Plan
    exec_plan_res = client.post(
        f"/recovery-plans/{plan_id}/execute",
        headers=headers
    )
    assert exec_plan_res.status_code == 200, exec_plan_res.text
    executed_plan = exec_plan_res.json()
    assert executed_plan["status"] == "COMPLETED"

    # 9. Verify Concrete Compensation Results
    status_res = client.get(
        f"/recovery-plans/{plan_id}/execution-status",
        headers=headers
    )
    assert status_res.status_code == 200, status_res.text
    exec_status = status_res.json()
    assert exec_status["completed_actions"] == 4
    assert exec_status["failed_actions"] == 0

    # Verify that actual compensation adapter executed
    for act in exec_status["actions"]:
        assert act["status"] == "COMPLETED"
        res_payload = act["result_payload"]
        assert res_payload is not None
        if act["action_type"] == "COMPENSATE":
            assert res_payload["adapter"] == "CompensationSimulationAdapter"
            assert res_payload["executed"] is True
            assert "reversal_reference" in res_payload["details"]
        elif act["action_type"] == "RETRY":
            assert res_payload["adapter"] == "RetrySimulationAdapter"
            assert res_payload["executed"] is True

    # 10. View Audit History
    audit_res = client.get(
        f"/api/v1/executions/{execution_id}/audit-events",
        headers=headers
    )
    assert audit_res.status_code == 200, audit_res.text
    events = audit_res.json()
    event_types = [e["event_type"] for e in events]

    assert "WORKFLOW_EXECUTION_FAILED" in event_types
    assert "RECOVERY_PLAN_GENERATED" in event_types
    assert "RECOVERY_PLAN_APPROVED" in event_types
    assert "RECOVERY_PLAN_EXECUTED" in event_types
    assert "RECOVERY_COMPENSATION_EXECUTED" in event_types
