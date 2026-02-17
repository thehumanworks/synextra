from typing import Final, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

STATUS_OK: Final[Literal["ok"]] = "ok"


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str


def build_health_router(*, service_name: str) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/health", response_model=HealthResponse, summary="Health check")
    async def health() -> HealthResponse:
        return HealthResponse(status=STATUS_OK, service=service_name)

    return router
