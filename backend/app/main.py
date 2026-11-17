import os
from fastapi.middleware.cors import CORSMiddleware


from fastapi import FastAPI, HTTPException

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine

from .api.auth import router as auth_router
from .api.workflows import router as workflows_router
from .api.executions import router as executions_router
from .api.recovery import router as recovery_router
from .api.audit import router as audit_router


app = FastAPI(
    title="UNDOX - Workflow Failure Recovery System",
    description=(
        "Workflow management and failure "
        "recovery platform"
    ),
    version="1.0.0"
)

# CORS configuration for local and Azure-hosted frontend.
_frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register all application routers
app.include_router(auth_router)
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(recovery_router)
app.include_router(audit_router)


# Home endpoint
@app.get("/")
def home():

    return {
        "message": "Welcome to UNDOX",
        "status": "Application is running"
    }


# Application health check
@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "application": "UNDOX"
    }


# Database health check
@app.get("/health/db")
def database_health():

    try:

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
            "database_name": "undox_dev"
        }

    except SQLAlchemyError:

        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )
