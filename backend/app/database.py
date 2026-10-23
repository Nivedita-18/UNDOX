"""
SQLAlchemy database setup and session management for UNDOX.
Uses the synchronous psycopg2 engine.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from backend.app.config import settings

# 1. Create the SQLAlchemy Engine
# pool_pre_ping=True checks connections for liveness before using them from the pool,
# preventing stale connection errors if PostgreSQL restarts.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# 2. Create the Session Factory
# autocommit=False ensures transactions are explicitly committed.
# autoflush=False avoids sending partial state to the DB before explicit commit/flush.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# 3. Declarative Base Class for Models
class Base(DeclarativeBase):
    """
    Base class for all future SQLAlchemy models in UNDOX.
    """
    pass


# 4. Dependency Injection for FastAPI endpoints
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request
    and guarantees it is closed when the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
