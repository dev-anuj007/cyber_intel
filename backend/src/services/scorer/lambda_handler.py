"""Scorer Microservice AWS Lambda Handler.

Wraps the Scorer sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.services.scorer.api import router as scorer_router
from src.services.scorer import default_scorer_service
from src.services.accounts import default_accounts_service
from src.core.error_handlers import register_error_handlers
from src.services.logger import get_logger

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

default_scorer_service.set_accounts_service(default_accounts_service)
app.include_router(scorer_router)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "service": "scorer-microservice",
        "model": default_scorer_service.model,
    }


handler = Mangum(app, lifespan="off")
