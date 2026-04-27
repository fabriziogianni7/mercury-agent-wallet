"""Sanitized FastAPI exception mapping for Mercury service endpoints."""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mercury.chains import UnsupportedChainError
from mercury.custody import CustodyError
from mercury.service.logging import log_service_event, redact_error_message, redact_value


class MercuryServiceError(RuntimeError):
    """Base class for errors that can be returned safely by the service."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_message = "Mercury request failed."

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        super().__init__(message or self.public_message)
        if status_code is not None:
            self.status_code = status_code


class DependencyUnavailableError(MercuryServiceError):
    """Raised when runtime dependencies cannot be constructed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    public_message = "Mercury dependencies are unavailable."


class GraphInvocationError(MercuryServiceError):
    """Raised when graph execution fails outside domain-normalized graph state."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_message = "Mercury graph invocation failed."


def install_exception_handlers(app: FastAPI) -> None:
    """Register sanitized exception handlers on a FastAPI app."""

    app.add_exception_handler(RequestValidationError, cast(Any, _validation_exception_handler))
    app.add_exception_handler(MercuryServiceError, cast(Any, _service_exception_handler))
    app.add_exception_handler(CustodyError, cast(Any, _custody_exception_handler))
    app.add_exception_handler(UnsupportedChainError, cast(Any, _chain_exception_handler))
    app.add_exception_handler(Exception, cast(Any, _unhandled_exception_handler))


async def _validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = _request_id(request)
    details = jsonable_encoder(redact_value(exc.errors()))
    log_service_event(
        "request_validation_error",
        level=logging.WARNING,
        request_id=request_id,
        path=request.url.path,
        errors=details,
    )
    return _error_response(
        request_id=request_id,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Request validation failed.",
        details=details,
    )


async def _service_exception_handler(request: Request, exc: MercuryServiceError) -> JSONResponse:
    request_id = _request_id(request)
    log_service_event(
        "service_error",
        level=logging.WARNING if exc.status_code < 500 else logging.ERROR,
        request_id=request_id,
        path=request.url.path,
        error=exc,
    )
    return _error_response(
        request_id=request_id,
        status_code=exc.status_code,
        message=redact_error_message(exc),
    )


async def _custody_exception_handler(request: Request, exc: CustodyError) -> JSONResponse:
    request_id = _request_id(request)
    log_service_event(
        "custody_error",
        level=logging.WARNING,
        request_id=request_id,
        path=request.url.path,
        error=exc,
    )
    return _error_response(
        request_id=request_id,
        status_code=status.HTTP_400_BAD_REQUEST,
        message=redact_error_message(exc),
    )


async def _chain_exception_handler(request: Request, exc: UnsupportedChainError) -> JSONResponse:
    request_id = _request_id(request)
    log_service_event(
        "chain_error",
        level=logging.WARNING,
        request_id=request_id,
        path=request.url.path,
        error=exc,
    )
    return _error_response(
        request_id=request_id,
        status_code=status.HTTP_400_BAD_REQUEST,
        message=redact_error_message(exc),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    log_service_event(
        "unhandled_error",
        level=logging.ERROR,
        request_id=request_id,
        path=request.url.path,
        error=exc,
    )
    return _error_response(
        request_id=request_id,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error.",
    )


def _error_response(
    *,
    request_id: str | None,
    status_code: int,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "request_id": request_id,
        "status": "error",
        "message": message,
        "error": {"message": message},
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None
