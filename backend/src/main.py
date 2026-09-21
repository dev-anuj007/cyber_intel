from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import ENVIRONMENT, LOGFIRE_TOKEN
from src.core.dependencies import get_accounts_service, get_database_service, init_core_services
from src.core.error_handlers import register_error_handlers
from src.services.accounts import accounts_router
from src.services.auth import auth_router
from src.services.crawler import crawler_router
from src.services.database import database_router, init_database
from src.services.eval import eval_router
from src.services.jobs import default_jobs_service, jobs_router
from src.services.logger import UserJourneyMiddleware, get_logger
from src.services.prompts import prompts_router
from src.services.scorer import scorer_router

logger = get_logger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Sales Intelligence Platform Services...", environment=ENVIRONMENT)
    try:
        init_database()
        logger.info("Relational schema initialized successfully")
        init_core_services()
        logger.info("Core microservices initialized")
        default_jobs_service.recover_stale_jobs()
        logger.info("Background jobs service initialized and stale jobs recovered")
    except Exception as e:
        logger.error(f"Error initializing services on startup: {e}")
        raise

    yield

    logger.info("Shutting down Sales Intelligence Platform Services...")


app = FastAPI(
    title="Sales Intelligence Platform",
    description="Microservice-First AI-powered B2B sales prospecting, JWT auth, and custom LLM inference scoring",
    version="2.0.0",
    lifespan=lifespan,
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
        logger.info("Logfire FastAPI instrumentation active")
    except Exception as e:
        logger.warning(f"Could not instrument FastAPI with Logfire: {e}")


@app.get("/", tags=["System Health"])
def root():
    return {
        "name": "Sales Intelligence Platform API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "message": "Welcome! Visit /docs for the interactive Swagger UI API documentation.",
    }


@app.get("/health", tags=["System Health"])
def health():
    accounts_service = get_accounts_service()
    db_service = get_database_service()
    stats = accounts_service.get_summary_stats()
    db_health = db_service.get_health()

    return {
        "status": "ok",
        "service_version": "2.0.0",
        "architecture": "microservice-serverless-lambda",
        "accounts_in_db": stats["total_accounts"],
        "database_storage": db_health.storage_location,
    }


app.include_router(database_router)
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(scorer_router)
app.include_router(crawler_router)
app.include_router(eval_router)
app.include_router(prompts_router)
app.include_router(jobs_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
