from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_payload(
    code: str,
    message: str,
    details: list[Any] | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "warnings": warnings or [],
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_by_status = {
            401: "unauthorized",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                code_by_status.get(exc.status_code, "http_error"),
                str(exc.detail),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "validation_error",
                "The request could not be validated.",
                details,
            ),
        )
