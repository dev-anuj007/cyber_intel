"""Unified Sales Intelligence Platform Gateway AWS Lambda Handler.

Wraps the full FastAPI application using Mangum for AWS Lambda execution.
"""

from mangum import Mangum
from src.main import app

# Unified Gateway ASGI Lambda Entrypoint
handler = Mangum(app, lifespan="off")
