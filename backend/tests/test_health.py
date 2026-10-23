"""
Tests for health check endpoints (/health and /health/db).
Unit tests use dependency overrides to remain isolated from external databases.
"""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db

client = TestClient(app)


def test_health_check_returns_200():
    """
    Ensure GET /health returns HTTP 200 OK.
    """
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_payload():
    """
    Ensure GET /health returns the expected JSON payload: {"status": "ok"}.
    """
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_db_success_mocked():
    """
    Ensure GET /health/db returns HTTP 200 and success payload when database query succeeds.
    Uses dependency override to isolate test execution from external database state.
    """
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}
    finally:
        app.dependency_overrides.clear()


def test_health_db_failure_mocked():
    """
    Ensure GET /health/db returns HTTP 503 when the database connection or query fails.
    Verifies that internal connection errors or credentials are not leaked.
    """
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Simulated connection refused")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database connection unavailable"}
    finally:
        app.dependency_overrides.clear()
