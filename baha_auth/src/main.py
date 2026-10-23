"""Ứng dụng FastAPI cho dịch vụ phân quyền BAHA Auth."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from baha_auth.src.api.approval_router import router as approval_router
from baha_auth.src.api.audit_router import router as audit_router
from baha_auth.src.api.evaluate_router import router as evaluate_router
from baha_auth.src.api.org_router import router as org_router
from baha_auth.src.api.role_router import router as role_router
from baha_auth.src.api.worker_router import router as worker_router
from baha_auth.src.config import settings
from baha_auth.src.database import init_db
from baha_auth.src.schemas.contracts import ErrorPayload


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Dịch vụ xác minh danh tính và phân quyền theo tenant của BAHA GROUP.",
    docs_url="/authz/docs",
    redoc_url="/authz/redoc",
    openapi_url="/authz/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-Id", "X-Request-Id"],
)


@app.get("/authz/healthz", tags=["Theo dõi trạng thái"])
def healthz():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    correlation_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    if isinstance(exc.detail, dict):
        err_code = exc.detail.get("error_code", "AUTHORIZATION_ERROR")
        message = exc.detail.get("message", "Yêu cầu không được chấp nhận.")
    else:
        err_code = "HTTP_ERROR"
        message = str(exc.detail)
    payload = ErrorPayload(
        error_code=err_code,
        message=message,
        correlation_id=correlation_id,
        policy_version=settings.policy_version,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(), headers=exc.headers)


app.include_router(org_router)
app.include_router(role_router)
app.include_router(evaluate_router)
app.include_router(approval_router)
app.include_router(worker_router)
app.include_router(audit_router)
