from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.core.config import LOGFIRE_TOKEN
from src.core.error_handlers import register_error_handlers
from src.services.crawler.api import router as crawler_router
from src.services.jobs.dependencies import get_jobs_service
from src.services.logger.logger_service import get_logger
from src.services.logger.middleware import UserJourneyMiddleware

logger = get_logger("services.crawler.lambda")

app = FastAPI(
    title="Crawler Microservice",
    description="Serverless microservice for web domain crawling, tech stack discovery, and intelligence aggregation",
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

app.include_router(crawler_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "crawler-microservice"}


_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    if isinstance(event, dict) and (
        "job_id" in event or event.get("action") == "execute_job"
    ):
        job_id = event.get("job_id")
        if job_id:
            logger.info(
                f"Executing background crawler job {job_id} via async Lambda event",
                job_id=str(job_id),
            )
            get_jobs_service().execute_job(str(job_id))
            return {"status": "completed", "job_id": str(job_id)}
    return _mangum_handler(event, context)
