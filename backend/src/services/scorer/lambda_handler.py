"""Scorer Microservice AWS Lambda Handler.

Wraps the Scorer sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.core.config import LOGFIRE_TOKEN
from src.core.error_handlers import register_error_handlers
from src.services.accounts import default_accounts_service
from src.services.logger import UserJourneyMiddleware, get_logger
from src.services.scorer import default_scorer_service
from src.services.scorer.api import router as scorer_router

logger = get_logger("services.scorer.lambda")

app = FastAPI(
    title="Scorer Microservice",
    description="Serverless microservice for LLM AI qualification scoring, risk assessment, and outreach synthesis",
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

default_scorer_service.set_accounts_service(default_accounts_service)
app.include_router(scorer_router)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "service": "scorer-microservice",
        "model": default_scorer_service.model,
    }


from src.services.jobs import default_jobs_service

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    if isinstance(event, dict) and ("job_id" in event or event.get("action") == "execute_job"):
        job_id = event.get("job_id")
        if job_id:
            logger.info(f"Executing background scorer job {job_id} via async Lambda event", job_id=str(job_id))
            default_jobs_service.execute_job(str(job_id))
            return {"status": "completed", "job_id": str(job_id)}
    return _mangum_handler(event, context)
