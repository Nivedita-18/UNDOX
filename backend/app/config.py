import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env. Existing Windows environment variables take priority.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Azure Database for PostgreSQL connection settings
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "").strip()
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "undox_dev").strip()
DB_SSLMODE = os.getenv("DB_SSLMODE", "require").strip().lower()

# Authentication settings
DEFAULT_SECRET_KEY = "local-development-only-secret-change-before-deployment"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

if not 1 <= DB_PORT <= 65535:
    raise ValueError("DB_PORT must be between 1 and 65535.")

if not 1 <= ACCESS_TOKEN_EXPIRE_MINUTES:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive.")

if DB_SSLMODE not in {
    "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
}:
    raise ValueError("Invalid DB_SSLMODE value.")

if ENVIRONMENT == "production":
    if SECRET_KEY == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "Production SECRET_KEY is not configured. Set a strong random "
            "SECRET_KEY in backend/.env."
        )
    if len(SECRET_KEY.encode("utf-8")) < 32:
        raise RuntimeError(
            "Production SECRET_KEY must contain at least 32 bytes."
        )