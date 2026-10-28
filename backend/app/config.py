"""
Configuration settings for the UNDOX backend.
Reads configuration from environment variables with safe development defaults.
"""

import os


class Settings:
    """
    Application settings.
    Values can be overridden using environment variables.
    """

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Database connection URL
    # Defaults to local PostgreSQL running on localhost:5432 with undox_dev database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://localhost:5432/undox_dev",
    )

    # Security & Authentication
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "undox-super-secret-key-change-in-production-2026",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    AUTH_ENFORCED: bool = os.getenv("UNDOX_AUTH_ENFORCED", "false").lower() in ("true", "1", "yes")


settings = Settings()
