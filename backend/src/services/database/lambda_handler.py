"""Database Microservice AWS Lambda Handler.

Wraps the Database FastAPI sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.core.config import LOGFIRE_TOKEN
from src.core.error_handlers import register_error_handlers
from src.services.database.api import get_db_service
from src.services.database.api import router as database_router
from src.services.logger import UserJourneyMiddleware, get_logger

logger = get_logger("services.database.lambda")

# Standalone microservice sub-app for Database Service
app = FastAPI(
    title="Database Microservice",
    description="Dedicated serverless microservice managing S3 direct accounts.db queries and connectivity",
    version="2.0.0",
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UserJourneyMiddleware)

if LOGFIRE_TOKEN:
    try:
        import logfire

        logfire.instrument_fastapi(app)
    except Exception:
        pass

app.include_router(database_router)


@app.on_event("startup")
def on_startup():
    db = get_db_service()
    try:
        db.init_schema()
        logger.info("Database microservice initialized successfully")
    except Exception as e:
        logger.warning(f"Database microservice schema check notice: {e}")


@app.get("/health", tags=["Health"])
def health():
    db = get_db_service()
    h = db.get_health()
    return {"status": "ok", "service": "database-microservice", "health": h}


# AWS Lambda ASGI Entrypoint
handler = Mangum(app, lifespan="off")
