from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import dev_auth
from app.api.router import api_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Liveness only - deliberately touches no dependencies."""
        return {"status": "ok"}

    app.include_router(api_router)
    if settings.local_sign_in:
        app.include_router(dev_auth.router)
    return app


app = create_app()
