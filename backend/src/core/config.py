import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SRC_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = SRC_DIR.parent

ROOT_DIR = (
    BACKEND_DIR.parent
    if (BACKEND_DIR.parent / "accounts.db").exists() or (BACKEND_DIR.parent / "frontend").exists()
    else Path(os.getenv("ROOT_DIR", str(BACKEND_DIR)))
)

# Database & S3 Storage Configuration
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
S3_DATABASE_URI = os.getenv("S3_DATABASE_URI", "")
DB_PATH = Path(
    os.getenv("DATABASE_PATH", str(ROOT_DIR / "accounts.db" if (ROOT_DIR / "accounts.db").exists() else "accounts.db"))
)

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-sales-intel-jwt-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "168"))

PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2.0")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

PRICING = {
    "input": float(os.getenv("PRICING_INPUT_PER_1M", "0.075")),
    "output": float(os.getenv("PRICING_OUTPUT_PER_1M", "0.30")),
}

DEFAULT_TRACE_DIR = Path(os.getenv("DEFAULT_TRACE_DIR", "/tmp/traces"))
SUMMARY_CACHE_TTL_SECONDS = float(os.getenv("SUMMARY_CACHE_TTL_SECONDS", "60.0"))

ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "local")).lower()
SERVICE_NAME = os.getenv("SERVICE_NAME", "sales-intel-api")
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
