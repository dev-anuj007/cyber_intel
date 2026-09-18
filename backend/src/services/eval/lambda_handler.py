"""Eval Microservice AWS Lambda Handler.

Wraps the Evaluation sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.services.eval.api import router as eval_router
from src.core.error_handlers import register_error_handlers
from src.services.logger import get_logger, UserJourneyMiddleware
from src.core.config import LOGFIRE_TOKEN

logger = get_logger("services.eval.lambda")

app = FastAPI(
    title="Eval Microservice",
    description="Serverless microservice for prompt evaluation benchmarks, regression testing, and scoring accuracy",
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

app.include_router(eval_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "eval-microservice"}


handler = Mangum(app, lifespan="off")
