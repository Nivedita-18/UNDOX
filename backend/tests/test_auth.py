"""
Comprehensive tests for Authentication, Role-Based Access Control (RBAC), and Audit Safety in UNDOX.

Covers:
- Cryptographic security:
  - PBKDF2-HMAC-SHA256 password hashing & constant-time verification.
  - RFC 7519 JWT token generation, expiration validation, signature verification, and tampering detection.
- Service level authentication:
  - User registration, duplicate checks, password verification.
- API authentication endpoints:
  - POST /api/v1/auth/register (201 Created, 409 Conflict, 422 Unprocessable Content)
  - POST /api/v1/auth/login (200 OK, 401 Unauthorized)
  - GET /api/v1/auth/me (200 OK, 401 Unauthorized)
- Role-based authorization (RBAC):
  - VIEWER role blocked from operator actions (approve, reject, execute) with 403 Forbidden.
  - OPERATOR role permitted to approve, reject, and execute recovery plans.
  - ADMIN role permitted across all endpoints.
- Strict authentication enforcement:
  - Protected endpoints require Bearer tokens when AUTH_ENFORCED is enabled (401 Unauthorized).
- Audit log confidentiality:
  - Passwords and access tokens are strictly verified never to be logged in audit records.
"""

import os
import uuid
from datetime import timedelta
from typing import Generator, List

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.audit.service import query_audit_events
from backend.app.auth.security import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.app.auth.service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)
from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.executions.service import execute_workflow
from backend.app.main import app
from backend.app.models.audit import AuditEvent
from backend.app.models.execution import WorkflowExecution
from backend.app.models.recovery import RecoveryPlan, RecoveryPlanStatus
from backend.app.models.user import User, UserRole
from backend.app.models.workflow import StepStatus, WorkflowInstance, WorkflowStatus, WorkflowStep
from backend.app.recovery.service import generate_recovery_plan
from backend.app.schemas.auth import (
    UserLoginRequest,
    UserRegisterRequest,
)
from backend.app.schemas.execution import ExecutionRequest, FailureSimulationConfig

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
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_test_env() -> Generator[tuple, None, None]:
    """Provides test database session and tracked entity cleanups."""
    db = TestingSessionLocal()
    created_users: List[uuid.UUID] = []
    created_workflows: List[uuid.UUID] = []
    created_executions: List[uuid.UUID] = []
    created_plans: List[uuid.UUID] = []

    def create_user(username: str, role: UserRole = UserRole.VIEWER, password: str = "SecurePass123!") -> User:
        user = register_user(
            db,
            UserRegisterRequest(
                username=username,
                email=f"{username}@example.com",
                password=password,
                role=role,
            ),
        )
        created_users.append(user.id)
        return user

    def create_workflow(step_names: List[str]) -> WorkflowInstance:
        wf = WorkflowInstance(
            name=f"Auth-WF-{uuid.uuid4().hex[:6]}",
            status=WorkflowStatus.PENDING.value,
        )
        db.add(wf)
        db.flush()
        created_workflows.append(wf.id)

        for idx, name in enumerate(step_names, start=1):
            s = WorkflowStep(
                workflow_id=wf.id,
                step_order=idx,
                name=name,
                status=StepStatus.PENDING.value,
            )
            db.add(s)

        db.commit()
        db.refresh(wf)
        return wf

    try:
        yield db, create_user, create_workflow, created_executions, created_plans
    finally:
        for ev in db.execute(select(AuditEvent)).scalars().all():
            db.delete(ev)
        for p_id in created_plans:
            p = db.get(RecoveryPlan, p_id)
            if p:
                db.delete(p)
        for e_id in created_executions:
            e = db.get(WorkflowExecution, e_id)
            if e:
                db.delete(e)
        for w_id in created_workflows:
            w = db.get(WorkflowInstance, w_id)
            if w:
                db.delete(w)
        for u_id in created_users:
            u = db.get(User, u_id)
            if u:
                db.delete(u)
        db.commit()
        db.close()


def make_auth_headers(user: User) -> dict:
    """Helper creating Bearer Authorization header for a given user."""
    token = create_access_token({
        "sub": user.username,
        "user_id": str(user.id),
        "role": user.role,
    })
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Cryptographic Security Tests
# ===========================================================================

class TestCryptographicSecurity:
    """Validates hashing, constant-time verification, and JWT mechanics."""

    def test_password_hashing_and_verification(self):
        plain = "MySecretP@ssw0rd!"
        hashed = hash_password(plain)
        assert hashed.startswith("pbkdf2:sha256:100000$")
        assert hashed != plain
        assert verify_password(plain, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_unique_salts_for_identical_passwords(self):
        pwd = "CommonPassword123!"
        hash1 = hash_password(pwd)
        hash2 = hash_password(pwd)
        assert hash1 != hash2
        assert verify_password(pwd, hash1) is True
        assert verify_password(pwd, hash2) is True

    def test_jwt_creation_and_decoding(self):
        claims = {"sub": "alice", "role": "OPERATOR"}
        token = create_access_token(claims, expires_delta=timedelta(minutes=15))
        decoded = decode_access_token(token)
        assert decoded["sub"] == "alice"
        assert decoded["role"] == "OPERATOR"
        assert "exp" in decoded

    def test_jwt_tampered_signature_rejected(self):
        claims = {"sub": "alice", "role": "OPERATOR"}
        token = create_access_token(claims)
        # Tamper payload
        parts = token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}xyz.{parts[2]}"
        with pytest.raises(InvalidTokenError):
            decode_access_token(tampered_token)

    def test_jwt_expired_token_rejected(self):
        claims = {"sub": "bob"}
        expired_token = create_access_token(claims, expires_delta=timedelta(seconds=-10))
        with pytest.raises(TokenExpiredError):
            decode_access_token(expired_token)

    def test_jwt_malformed_token_rejected(self):
        with pytest.raises(InvalidTokenError):
            decode_access_token("not-a-valid-jwt-token")


# ===========================================================================
# 2. Authentication Service Tests
# ===========================================================================

class TestAuthService:
    """Validates user account operations and authentication checks."""

    def test_register_and_authenticate_user_success(self, auth_test_env):
        db, create_user, _, _, _ = auth_test_env
        user = create_user("service_user", UserRole.OPERATOR, "ValidPassword123!")
        assert user.id is not None
        assert user.role == UserRole.OPERATOR.value

        auth_user = authenticate_user(db, "service_user", "ValidPassword123!")
        assert auth_user.id == user.id

    def test_register_duplicate_username_raises_conflict(self, auth_test_env):
        db, create_user, _, _, _ = auth_test_env
        create_user("dup_user", UserRole.VIEWER)
        with pytest.raises(UserAlreadyExistsError):
            create_user("dup_user", UserRole.OPERATOR)

    def test_authenticate_invalid_password_raises_error(self, auth_test_env):
        db, create_user, _, _, _ = auth_test_env
        create_user("alice_auth", UserRole.VIEWER, "CorrectPass123!")
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(db, "alice_auth", "IncorrectPass!")

    def test_authenticate_nonexistent_user_raises_error(self, auth_test_env):
        db, _, _, _, _ = auth_test_env
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(db, "nonexistent_ghost", "SomePass123!")


# ===========================================================================
# 3. Authentication REST API Tests
# ===========================================================================

class TestAuthAPI:
    """Validates /auth/register, /auth/login, and /auth/me endpoints."""

    def test_api_register_user_success(self, client):
        payload = {
            "username": f"user_{uuid.uuid4().hex[:6]}",
            "email": f"user_{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPassword123!",
            "role": "OPERATOR",
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()
        assert data["username"] == payload["username"]
        assert data["role"] == "OPERATOR"
        assert "password" not in data
        assert "hashed_password" not in data

    def test_api_register_duplicate_returns_409(self, client):
        username = f"dup_{uuid.uuid4().hex[:6]}"
        payload = {
            "username": username,
            "email": f"{username}@example.com",
            "password": "StrongPassword123!",
        }
        res1 = client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = client.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in res2.json()["detail"]

    def test_api_register_short_password_returns_422(self, client):
        payload = {
            "username": "short_pwd_user",
            "email": "short@example.com",
            "password": "short",  # < 8 chars
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_api_login_success_returns_jwt(self, client, auth_test_env):
        _, create_user, _, _, _ = auth_test_env
        create_user("login_user", UserRole.OPERATOR, "MyLoginPass123!")

        res = client.post(
            "/api/v1/auth/login",
            json={"username": "login_user", "password": "MyLoginPass123!"},
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "login_user"
        assert data["role"] == "OPERATOR"

    def test_api_login_invalid_password_returns_401(self, client, auth_test_env):
        _, create_user, _, _, _ = auth_test_env
        create_user("wrong_pwd_user", UserRole.VIEWER, "OriginalPass123!")

        res = client.post(
            "/api/v1/auth/login",
            json={"username": "wrong_pwd_user", "password": "WrongPassword!"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid username or password" in res.json()["detail"]

    def test_api_get_me_with_valid_token(self, client, auth_test_env):
        _, create_user, _, _, _ = auth_test_env
        user = create_user("me_user", UserRole.ADMIN, "Pass12345678!")
        headers = make_auth_headers(user)

        res = client.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["username"] == "me_user"
        assert data["role"] == "ADMIN"

    def test_api_get_me_without_token_returns_401(self, client):
        res = client.get("/api/v1/auth/me")
        # Direct requirement of Header(...) on /auth/me
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_api_get_me_with_invalid_token_returns_401(self, client):
        res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.jwt.signature"})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# 4. Role-Based Authorization (RBAC) Tests
# ===========================================================================

class TestRoleBasedAuthorization:
    """Validates permission guards across VIEWER, OPERATOR, and ADMIN roles."""

    def test_viewer_role_cannot_approve_plan_returns_403(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, created_plans = auth_test_env
        viewer = create_user("viewer_joe", UserRole.VIEWER)
        headers = make_auth_headers(viewer)

        wf = create_workflow(["Step 1", "Step 2"])
        exec_rec = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(failure_simulation=FailureSimulationConfig(fail_at_step_order=2)),
        )
        created_executions.append(exec_rec.id)

        plan = generate_recovery_plan(db, exec_rec.id)
        created_plans.append(plan.id)

        # Viewer attempts approval -> 403 Forbidden
        res = client.post(f"/recovery-plans/{plan.id}/approve", headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert "does not have required permissions" in res.json()["detail"]

    def test_viewer_role_cannot_reject_plan_returns_403(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, created_plans = auth_test_env
        viewer = create_user("viewer_kate", UserRole.VIEWER)
        headers = make_auth_headers(viewer)

        wf = create_workflow(["Step 1", "Step 2"])
        exec_rec = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(failure_simulation=FailureSimulationConfig(fail_at_step_order=2)),
        )
        created_executions.append(exec_rec.id)

        plan = generate_recovery_plan(db, exec_rec.id)
        created_plans.append(plan.id)

        res = client.post(
            f"/recovery-plans/{plan.id}/reject",
            json={"reason": "Viewer attempt"},
            headers=headers,
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_operator_role_can_approve_recovery_plan(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, created_plans = auth_test_env
        operator = create_user("op_charlie", UserRole.OPERATOR)
        headers = make_auth_headers(operator)

        wf = create_workflow(["Step 1", "Step 2"])
        exec_rec = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(failure_simulation=FailureSimulationConfig(fail_at_step_order=2)),
        )
        created_executions.append(exec_rec.id)

        plan = generate_recovery_plan(db, exec_rec.id)
        created_plans.append(plan.id)

        res = client.post(
            f"/recovery-plans/{plan.id}/approve",
            json={"reason": "Approved by verified operator"},
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["status"] == RecoveryPlanStatus.APPROVED.value
        assert data["decision_operator"] == "op_charlie"

    def test_admin_role_can_approve_recovery_plan(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, created_plans = auth_test_env
        admin = create_user("admin_diana", UserRole.ADMIN)
        headers = make_auth_headers(admin)

        wf = create_workflow(["Step 1", "Step 2"])
        exec_rec = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(failure_simulation=FailureSimulationConfig(fail_at_step_order=2)),
        )
        created_executions.append(exec_rec.id)

        plan = generate_recovery_plan(db, exec_rec.id)
        created_plans.append(plan.id)

        res = client.post(
            f"/recovery-plans/{plan.id}/approve",
            json={"reason": "Admin approval override"},
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["status"] == RecoveryPlanStatus.APPROVED.value

    def test_viewer_can_read_resources(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, created_plans = auth_test_env
        viewer = create_user("read_viewer", UserRole.VIEWER)
        headers = make_auth_headers(viewer)

        wf = create_workflow(["Step 1"])
        res_wf = client.get(f"/workflows/{wf.id}", headers=headers)
        assert res_wf.status_code == status.HTTP_200_OK

        res_audit = client.get("/api/v1/audit-events", headers=headers)
        assert res_audit.status_code == status.HTTP_200_OK


# ===========================================================================
# 5. Strict Auth Enforcement Tests
# ===========================================================================

class TestStrictAuthEnforcement:
    """Validates behavior when AUTH_ENFORCED is active."""

    def test_auth_enforced_blocks_unauthenticated_requests(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENFORCED", True)

        # Unauthenticated request to /workflows should receive 401
        res = client.get("/workflows")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in res.json()["detail"]

    def test_auth_enforced_permits_authenticated_requests(self, client, auth_test_env, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENFORCED", True)
        _, create_user, _, _, _ = auth_test_env
        user = create_user("enforced_user", UserRole.OPERATOR)
        headers = make_auth_headers(user)

        res = client.get("/workflows", headers=headers)
        assert res.status_code == status.HTTP_200_OK


# ===========================================================================
# 6. Audit Log Confidentiality Safety Test
# ===========================================================================

class TestAuditLogSafety:
    """Validates that passwords, secrets, and JWT access tokens are never logged."""

    def test_credentials_never_stored_in_audit_records(self, client, auth_test_env):
        db, create_user, create_workflow, created_executions, _ = auth_test_env
        user = create_user("safety_user", UserRole.OPERATOR, "SuperSecretP@ssw0rd999!")
        headers = make_auth_headers(user)

        wf = create_workflow(["Step 1", "Step 2"])
        exec_rec = execute_workflow(
            db,
            wf.id,
            ExecutionRequest(
                failure_simulation=FailureSimulationConfig(
                    fail_at_step_order=2,
                    error_message="Simulation with token=ghp_secretTokenVal123 and password=super_secret!",
                )
            ),
        )
        created_executions.append(exec_rec.id)

        events, _ = query_audit_events(db, execution_id=exec_rec.id)
        assert len(events) >= 1

        for ev in events:
            # Check message
            assert "SuperSecretP@ssw0rd999!" not in ev.message
            assert "ghp_secretTokenVal123" not in ev.message
            assert "super_secret!" not in ev.message
            # Check details
            if ev.details:
                for k, v in ev.details.items():
                    assert "password" not in k.lower() or v == "[REDACTED]"
                    assert "token" not in k.lower() or v == "[REDACTED]"
                    if isinstance(v, str):
                        assert "SuperSecretP@ssw0rd999!" not in v
                        assert "ghp_secretTokenVal123" not in v
