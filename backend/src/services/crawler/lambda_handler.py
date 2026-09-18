"""Crawler Microservice AWS Lambda Handler.

Wraps the Crawler sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.services.crawler.api import router as crawler_router
from src.services.crawler import default_crawler_service
from src.services.accounts import default_accounts_service
from src.core.error_handlers import register_error_handlers
from src.services.logger import get_logger

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

default_crawler_service.set_accounts_service(default_accounts_service)
app.include_router(crawler_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "crawler-microservice"}


handler = Mangum(app, lifespan="off")
