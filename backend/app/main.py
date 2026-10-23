"""
UNDOX — Workflow Failure Recovery System
Main FastAPI Application Entry Point
"""

from fastapi import FastAPI

app = FastAPI(
    title="UNDOX API",
    description="Workflow Failure Recovery System API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Used by load balancers, monitoring tools, and tests to verify the server is running.
    """
    return {"status": "ok"}
