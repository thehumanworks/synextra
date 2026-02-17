import os
from typing import Final

import uvicorn
from fastapi import FastAPI

from synextra_backend.api import build_health_router

DEFAULT_SERVICE_NAME: Final[str] = "synextra-backend"
DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 8000


def create_app(*, service_name: str = DEFAULT_SERVICE_NAME) -> FastAPI:
    normalized_service_name = service_name.strip()
    if not normalized_service_name:
        raise ValueError("service_name must not be empty")

    app = FastAPI(
        title="synextra-backend",
        version="0.1.0",
    )
    app.include_router(build_health_router(service_name=normalized_service_name))
    return app


app = create_app()


def _read_server_host() -> str:
    configured_host = os.getenv("SYNEXTRA_BACKEND_HOST", DEFAULT_HOST).strip()
    if not configured_host:
        raise ValueError("SYNEXTRA_BACKEND_HOST must not be empty")

    return configured_host


def _read_server_port() -> int:
    configured_port = os.getenv("SYNEXTRA_BACKEND_PORT", str(DEFAULT_PORT)).strip()
    if not configured_port:
        raise ValueError("SYNEXTRA_BACKEND_PORT must not be empty")

    port = int(configured_port)
    if port <= 0:
        raise ValueError("SYNEXTRA_BACKEND_PORT must be greater than zero")

    return port


def main() -> None:
    uvicorn.run(
        "synextra_backend.app:app",
        host=_read_server_host(),
        port=_read_server_port(),
        reload=False,
    )
