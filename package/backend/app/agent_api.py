import logging
import re
import secrets
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routes.agent import router


logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", secrets.token_hex(12))


def _error_code(status_code: int) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "authentication_required"
    if status_code == 403:
        return "permission_denied"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "not_ready"
    if status_code == 413:
        return "payload_too_large"
    if status_code == 422:
        return "validation_error"
    if status_code == 429:
        return "queue_limit_reached"
    return "request_failed"


def create_agent_app() -> FastAPI:
    agent_app = FastAPI(
        title="Wenheng Agent API",
        description=(
            "Versioned asynchronous API for text polishing, format-preserving "
            "document processing, batch queues, and result downloads."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "system", "description": "Capabilities and runtime limits"},
            {"name": "tasks", "description": "Create and control individual tasks"},
            {"name": "batches", "description": "Create and monitor file batches"},
            {"name": "results", "description": "Download completed results"},
        ],
    )

    @agent_app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        supplied = (request.headers.get("X-Request-ID") or "").strip()
        request.state.request_id = (
            supplied
            if REQUEST_ID_PATTERN.fullmatch(supplied)
            else secrets.token_hex(12)
        )
        started_at = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            "agent_api request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started_at) * 1000,
        )
        return response

    @agent_app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Request failed"
        headers = dict(exc.headers or {})
        if exc.status_code == 401:
            headers.setdefault("WWW-Authenticate", "Bearer")
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": _error_code(exc.status_code),
                        "message": message,
                        "details": None if isinstance(detail, str) else detail,
                        "request_id": _request_id(request),
                    }
                }
            ),
        )

    @agent_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Request validation failed",
                        "details": exc.errors(),
                        "request_id": _request_id(request),
                    }
                }
            ),
        )

    @agent_app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled Agent API error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal server error",
                    "details": None,
                    "request_id": _request_id(request),
                }
            },
        )

    @agent_app.get("/", include_in_schema=False)
    async def api_index():
        return {
            "name": "Wenheng Agent API",
            "version": "v1",
            "docs": "/api/v1/agent/docs",
            "openapi": "/api/v1/agent/openapi.json",
        }

    @agent_app.get("/health", tags=["system"], summary="Agent API health check")
    async def health():
        return {"status": "healthy", "api_version": "v1"}

    agent_app.include_router(router)
    return agent_app
