import os
import importlib
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Avoid importing 'fastapi' during static analysis in environments where it's not installed;
    # declare these names for type checkers to prevent editor/linter "could not be resolved" errors.
    FastAPI: Any
    HTTPException: Any
    CORSMiddleware: Any
    StaticFiles: Any
else:
    try:
        fastapi_mod = importlib.import_module("fastapi")
        FastAPI = fastapi_mod.FastAPI
        HTTPException = fastapi_mod.HTTPException
        cors_mod = importlib.import_module("fastapi.middleware.cors")
        CORSMiddleware = getattr(cors_mod, "CORSMiddleware")
        static_mod = importlib.import_module("fastapi.staticfiles")
        StaticFiles = getattr(static_mod, "StaticFiles")
    except Exception as e:
        raise ImportError("fastapi and its subpackages are required. Install with 'pip install fastapi[all]'") from e

from backend.api import router as api_router, ai_router
from backend.ws_api import router as ws_router
from backend.routes.auth_routes import auth_router
from backend.routes.billing_routes import billing_router
from backend.routes.library_routes import library_router
from backend.routes.reader_routes import reader_router
from backend.adapters.azure_openai import AzureCognitiveTokenProvider
from backend.core.config import settings

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up token to fail-fast on bad identity/env.
    provider = AzureCognitiveTokenProvider()
    try:
        await provider.get_token()
        logger.info("AAD token warmup successful.")
    except Exception as exc:
        logger.warning("AAD warmup failed: %s", exc)  # do not crash; surfacing at first request is fine
    finally:
        await provider.aclose()
    yield
    # Cleanup is handled per adapter if you extend

app = FastAPI(
    title="Quantum Nexus Forge API",
    version="1.0.0",
    description="FastAPI backend exposing QuantumNexusForge operations with a service layer.",
    lifespan=lifespan,
)

# Add CORS — environment-aware
cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=bool(settings.API_KEY),
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

# REST API routes under /api
app.include_router(api_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(reader_router, prefix="/api")

# WebSocket routes (no prefix needed)
app.include_router(ws_router)

# Static UI (optional): serve ./frontend at /ui when present
try:
    import os as _os
    if _os.path.isdir("frontend"):
        app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")
except Exception:
    # Non-fatal if static files aren't available
    pass

@app.get("/")
async def root():
    return {"service": "Quantum Nexus Forge", "docs": "/docs"}

# Health (replaces old status)
@app.get("/api/status")
async def status():
    return {"ok": True, "adapter": "azure-openai", "api_version": settings.AOAI_API_VERSION}

# NOTE: The old RateLimiter and API Key middleware from the previous version have been removed.
# This logic is now handled by the dependency-injected `api_key_guard` in the AI router
# and the optional RATE_LIMIT_QPS setting in the new configuration model.
