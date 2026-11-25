from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import (
    DATABASE_URL_ENV,
    DB_USER,
    DB_PASSWORD,
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_SSLMODE,
)

if DATABASE_URL_ENV:
    url_str = DATABASE_URL_ENV
    if url_str.startswith("postgres://"):
        url_str = url_str.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+psycopg2://", 1)
    DATABASE_URL = url_str
else:
    if not DB_HOST or not DB_USER or not DB_PASSWORD:
        raise RuntimeError(
            "PostgreSQL settings are missing. Configure DATABASE_URL or DB_HOST, DB_USER and DB_PASSWORD."
        )

    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        query={"sslmode": DB_SSLMODE},
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()