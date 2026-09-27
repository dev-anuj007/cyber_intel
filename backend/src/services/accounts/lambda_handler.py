from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.core.config import LOGFIRE_TOKEN
from src.core.error_handlers import register_error_handlers
from src.services.accounts.api import router as accounts_router
from src.services.accounts.dependencies import default_accounts_service
from src.services.logger.logger_service import get_logger
from src.services.logger.middleware import UserJourneyMiddleware

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
app.add_middleware(UserJourneyMiddleware)

if LOGFIRE_TOKEN:
    try:
        import logfire

        logfire.instrument_fastapi(app)
    except Exception:
        pass

app.include_router(accounts_router)


@app.get("/health", tags=["Health"])
def health():
    stats = default_accounts_service.get_summary_stats()
    return {"status": "ok", "service": "accounts-microservice", "stats": stats}


handler = Mangum(app, lifespan="off")
