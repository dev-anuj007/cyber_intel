"""Auth Microservice AWS Lambda Handler.

Wraps the Authentication sub-application using Mangum for AWS Lambda execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.core.config import LOGFIRE_TOKEN
from src.core.error_handlers import register_error_handlers
from src.services.auth.api import router as auth_router
from src.services.logger import UserJourneyMiddleware, get_logger

logger = get_logger("services.auth.lambda")

app = FastAPI(
    title="Auth Microservice",
    description="Serverless microservice for user registration, JWT authentication, and secure password hashing",
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

app.include_router(auth_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "auth-microservice"}


handler = Mangum(app, lifespan="off")
