from mangum import Mangum
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.services.prompts.api import router as prompts_router

app = FastAPI(
    title="Prompt Registry Microservice",
    description="Dedicated serverless microservice for managing versioned LLM prompt templates and registries.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prompts_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "prompts",
    }


handler = Mangum(app, lifespan="off")
