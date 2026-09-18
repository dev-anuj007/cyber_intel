"""Accounts Microservice AWS Lambda Handler.

Wraps the Accounts sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.services.accounts.api import router as accounts_router
from src.services.accounts import default_accounts_service
from src.core.error_handlers import register_error_handlers
from src.services.logger import get_logger

logger = get_logger("services.accounts.lambda")

app = FastAPI(
    title="Accounts Microservice",
    description="Serverless microservice for B2B accounts prospecting, filtering, tiering, and CSV exports",
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

app.include_router(accounts_router)


@app.get("/health", tags=["Health"])
def health():
    stats = default_accounts_service.get_summary_stats()
    return {"status": "ok", "service": "accounts-microservice", "stats": stats}


handler = Mangum(app, lifespan="off")
