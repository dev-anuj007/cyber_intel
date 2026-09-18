"""Jobs Microservice AWS Lambda Handler.

Wraps the Background Jobs sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.services.jobs.api import router as jobs_router
from src.services.jobs import default_jobs_service
from src.core.error_handlers import register_error_handlers
from src.services.logger import get_logger, UserJourneyMiddleware
from src.core.config import LOGFIRE_TOKEN

logger = get_logger("services.jobs.lambda")

app = FastAPI(
    title="Jobs Microservice",
    description="Serverless microservice for asynchronous bulk jobs, progress tracking, and batch scoring",
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

app.include_router(jobs_router)


@app.on_event("startup")
def on_startup():
    try:
        default_jobs_service.recover_stale_jobs()
        logger.info("Jobs microservice initialized and stale jobs checked")
    except Exception as e:
        logger.warning(f"Jobs recovery check notice: {e}")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "jobs-microservice"}


handler = Mangum(app, lifespan="off")
