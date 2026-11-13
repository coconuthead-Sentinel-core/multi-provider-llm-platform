import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router as api_router, ai_router
from .ws_api import router as ws_router
from .routes.auth_routes import auth_router
from .routes.billing_routes import billing_router
from .adapters.azure_openai import AzureCognitiveTokenProvider
from .infrastructure.cosmos_repo import CosmosDBRepository
from .infrastructure.user_repository import user_repository
from .middleware import RequestSizeLimitMiddleware
from .core.config import settings, validate_security_configuration
from .core.logging_config import setup_logging
import uvicorn

# Initialize structured logging (JSON in production, human-readable in dev)
setup_logging()
logger = logging.getLogger("sentinel-middleware")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on missing production secrets (API key + JWT secret).
    validate_security_configuration()

    # Initialize Cosmos DB Repository (will use Mock DB mode if unavailable)
    await CosmosDBRepository.initialize()
    logger.info("Cosmos DB Repository initialized.")

    user_repository.initialize()
    logger.info("User repository initialized.")

    # Warm up token to fail-fast on bad identity/env.
    provider = AzureCognitiveTokenProvider()
    try:
        await provider.get_token()
        logger.info("AAD token warmup successful.")
    except Exception as exc:
        logger.warning("AAD warmup failed: %s", exc)
    finally:
        await provider.aclose()

    yield

    # Cleanup on shutdown
    user_repository.close()
    await CosmosDBRepository.close()
    logger.info("Shutdown complete.")


app = FastAPI(title="Sentinel Forge", version=settings.VERSION, lifespan=lifespan)

# --- Middleware (order matters: last added = first executed) ---

# 1. Request size limit — reject oversized payloads before processing
app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)

# 2. CORS — environment-aware origin restrictions
cors_origins = settings.cors_origin_list
logger.info("CORS allowed origins: %s", cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=bool(settings.API_KEY),
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(ws_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",  # nosec B104 - container deployments must bind all interfaces
        port=8000,
        timeout_keep_alive=75,
        log_level="info",
    )
