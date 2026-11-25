import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.database import SessionLocal
from app.models import User

client = TestClient(app)

def create_user(role="VIEWER"):
    email = f"user_{role.lower()}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    reg = client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201

    if role != "VIEWER":
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            user.role = role
            db.commit()

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_rbac_restrictions():
    viewer_headers = create_user(role="VIEWER")
    admin_headers = create_user(role="ADMIN")

    # 1. VIEWER cannot create workflow -> 403 Forbidden
    res_wf = client.post(
        "/workflows",
        json={
            "name": "Viewer Forbidden Workflow",
            "steps": [{"name": "Step 1", "step_order": 1, "payload": {}}]
        },
        headers=viewer_headers
    )
    assert res_wf.status_code == 403

    # 2. ADMIN can create workflow
    res_wf_admin = client.post(
        "/workflows",
        json={
            "name": f"Admin Workflow {uuid.uuid4().hex[:6]}",
            "steps": [{"name": "Step 1", "step_order": 1, "payload": {}}]
        },
        headers=admin_headers
    )
    assert res_wf_admin.status_code == 201
    wf_id = res_wf_admin.json()["id"]

    # 3. VIEWER cannot execute workflow -> 403 Forbidden
    res_exec = client.post(
        f"/workflows/{wf_id}/execute",
        json={"simulate_failure": False},
        headers=viewer_headers
    )
    assert res_exec.status_code == 403

    # 4. VIEWER cannot access audit events -> 403 Forbidden
    res_audit = client.get("/api/v1/audit-events", headers=viewer_headers)
    assert res_audit.status_code == 403

    # 5. ADMIN can access audit events
    res_audit_admin = client.get("/api/v1/audit-events", headers=admin_headers)
    assert res_audit_admin.status_code == 200


def test_recovery_rejection():
    operator_headers = create_user(role="OPERATOR")

    # Create & fail workflow
    wf_res = client.post(
        "/workflows",
        json={
            "name": f"Rejection Test Workflow {uuid.uuid4().hex[:6]}",
            "steps": [{"name": "Step 1", "step_order": 1, "payload": {}}]
        },
        headers=operator_headers
    )
    wf_id = wf_res.json()["id"]

    exec_res = client.post(
        f"/workflows/{wf_id}/execute",
        json={"simulate_failure": True, "failure_step_order": 1},
        headers=operator_headers
    )
    exec_id = exec_res.json()["id"]

    # Generate plan
    plan_res = client.post(f"/executions/{exec_id}/recovery-plans", headers=operator_headers)
    plan_id = plan_res.json()["id"]

    # Reject plan
    reject_res = client.post(
        f"/recovery-plans/{plan_id}/reject",
        json={"reason": "Operator rejected this recovery proposal due to manual policy override."},
        headers=operator_headers
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"

    # Attempting to execute rejected plan must fail
    try_exec = client.post(f"/recovery-plans/{plan_id}/execute", headers=operator_headers)
    assert try_exec.status_code == 400 or try_exec.status_code == 409
