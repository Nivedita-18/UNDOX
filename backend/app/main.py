"""
UNDOX — Workflow Failure Recovery System
Main FastAPI Application Entry Point
"""

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.api.workflows import router as workflows_router
from backend.app.api.executions import router as executions_router
from backend.app.api.recovery import router as recovery_router
from backend.app.api.audit import router as audit_router
from backend.app.api.auth import router as auth_router
from backend.app.database import get_db

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="UNDOX API",
    description="Workflow Failure Recovery System API",
    version="0.1.0",
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(recovery_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """
    Application health check endpoint.
    Verifies that the API server is responding.
    """
    return {"status": "ok"}


@app.get("/health/db")
def health_db_check(db: Session = Depends(get_db)):
    """
    Database health check endpoint.
    Executes a lightweight query (SELECT 1) to verify database connectivity.
    Returns HTTP 503 if the database is unreachable without leaking credentials.
    """
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            raise ValueError("Unexpected query result")
        return {"status": "ok", "database": "connected"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
