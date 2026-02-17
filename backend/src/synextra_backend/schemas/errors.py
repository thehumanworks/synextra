from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiError(BaseModel):
    """Normalized error payload returned by non-2xx endpoints.

    The frontend expects a stable shape that can be logged and surfaced in a
    recoverable way.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-friendly error message")
    recoverable: bool = Field(
        ..., description="Whether the client can retry without changing input"
    )
    request_id: str = Field(..., description="Per-request correlation identifier")


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ApiError


def new_request_id() -> str:
    return uuid.uuid4().hex


def error_response(
    *,
    code: str,
    message: str,
    recoverable: bool,
    request_id: str | None = None,
) -> ApiErrorResponse:
    return ApiErrorResponse(
        error=ApiError(
            code=code,
            message=message,
            recoverable=recoverable,
            request_id=request_id or new_request_id(),
        )
    )
