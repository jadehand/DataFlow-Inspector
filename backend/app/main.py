from __future__ import annotations

import json
import logging
import time
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    assistant_router,
    catalog_router,
    compare_router,
    health_router,
    imports_router,
    metadata_router,
    projects_router,
)
from .db.connection import ensure_data_dirs
from .db.schema_version import apply_migrations
from .tasks.import_tasks import worker

logger = logging.getLogger("dataflow_inspector")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="DataFlow Inspector API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(?:127\.0\.0\.1|localhost):(?!8080$)\d{1,5}$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed method=%s path=%s request_id=%s elapsed_ms=%s",
                request.method,
                request.url.path,
                request_id,
                elapsed_ms,
            )
            raise
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(round((time.perf_counter() - started) * 1000, 2))
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": detail,
                "detail": detail,
                "status_code": exc.status_code,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        detail = json.dumps(exc.errors(), ensure_ascii=False)
        return JSONResponse(
            status_code=422,
            content={
                "error": "request validation failed",
                "detail": detail,
                "status_code": 422,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_error method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal server error",
                "detail": str(exc),
                "status_code": 500,
                "request_id": request_id,
                "trace_hint": traceback.format_exception_only(type(exc), exc)[-1].strip(),
            },
        )

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        worker.start()
        app.state.import_worker = worker

    @app.on_event("shutdown")
    def shutdown() -> None:
        worker.stop()

    for router in [
        health_router,
        projects_router,
        imports_router,
        catalog_router,
        metadata_router,
        compare_router,
        assistant_router,
    ]:
        app.include_router(router)
    return app


def init_db() -> None:
    ensure_data_dirs()
    apply_migrations()


app = create_app()
