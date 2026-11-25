import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoints():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "Application is running"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_db = client.get("/health/db")
    assert res_db.status_code == 200
    assert res_db.json()["database"] == "connected"


def test_auth_registration_and_login():
    email = f"test_user_{pytest.importorskip('uuid').uuid4().hex[:8]}@example.com"
    password = "StrongTestPassword123!"

    # 1. Register
    reg_res = client.post("/auth/register", json={"email": email, "password": password})
    assert reg_res.status_code == 201, reg_res.text
    user_data = reg_res.json()
    assert user_data["email"] == email
    assert user_data["role"] == "VIEWER"
    assert user_data["is_active"] is True

    # 2. Duplicate registration
    dup_res = client.post("/auth/register", json={"email": email, "password": password})
    assert dup_res.status_code == 409

    # 3. Invalid login
    bad_login = client.post("/auth/login", json={"email": email, "password": "WrongPassword"})
    assert bad_login.status_code == 401

    # 4. Valid login
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 5. /auth/me
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert me_data["role"] == "VIEWER"
