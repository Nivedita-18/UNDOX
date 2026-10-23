"""
Tests for the health check endpoint.
Verifies the basic FastAPI application is responding correctly without needing a database.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

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
