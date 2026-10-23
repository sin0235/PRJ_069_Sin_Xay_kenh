# Ứng dụng chính FastAPI cho SIN Content Intelligence API
import uuid
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import check_db_ready, engine, Base
from src.schemas.contracts import HealthResponse, ReadyResponse, ErrorPayload
from src.modules.workspaces.router import router as workspaces_router
from src.modules.briefs.router import router as briefs_router
from src.modules.sources.router import router as sources_router
from src.modules.ingestion.router import router as ingestion_router
from src.modules.research.router import router as research_router
from src.modules.understanding.router import router as understanding_router
from src.modules.retrieval.router import router as retrieval_router
from src.modules.ideation.router import router as ideation_router
from src.modules.scripts.router import router as scripts_router
from src.modules.feedback.router import router as feedback_router
from src.modules.staging_reliability.router import router as staging_router
from src.modules.canary_rollback.router import router as canary_router
from src.modules.media_studio.router import media_router, jobs_router
from src.modules.auth.router import auth_router
from src.modules.platform_config.router import router as platform_config_router
from src.modules.dieu_phoi_dung.bo_dinh_tuyen import router as dieu_phoi_router

# Exception handler chuẩn hóa theo ErrorPayload
def _auto_start_9router_if_needed():
    """Tu dong kiem tra va khoi dong 9Router Gateway tren cong 20128 khi backend chay."""
    import os, socket, subprocess, shutil
    if os.environ.get("TESTING") == "1":
        return
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(("127.0.0.1", 20128))
        sock.close()
        if res != 0:
            cmd = shutil.which("9router") or shutil.which("9router.cmd")
            if cmd:
                subprocess.Popen([cmd, "-n", "--skip-update"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["npx", "--yes", "9router", "-n", "--skip-update"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

async def lifespan(app: FastAPI):
    # Khởi tạo bảng trong chế độ offline nếu chưa có
    Base.metadata.create_all(bind=engine)
    _auto_start_9router_if_needed()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Hệ thống nghiên cứu nội dung TikTok có căn cứ, sinh ý tưởng & kịch bản (PRJ_069)",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz", response_model=HealthResponse, tags=["Observability"])
def healthz():
    """Liveness probe: Kiểm tra dịch vụ API đang chạy bình thường"""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env
    )

@app.get("/readyz", response_model=ReadyResponse, tags=["Observability"])
def readyz():
    """Readiness probe: Kiểm tra database và các thành phần phụ thuộc sẵn sàng tiếp nhận traffic"""
    is_ready = check_db_ready()
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database_connected": False,
                "offline_mode": settings.app_env == "offline",
                "version": settings.app_version
            }
        )
    return ReadyResponse(
        status="ready",
        database_connected=True,
        offline_mode=settings.app_env == "offline",
        version=settings.app_version
    )

# Exception handler chuẩn hóa theo ErrorPayload
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    correlation_id = str(uuid.uuid4())
    
    if isinstance(exc.detail, dict):
        err_code = exc.detail.get("error_code", "HTTP_ERROR")
        msg = exc.detail.get("message") or exc.detail.get("message_safe", str(exc.detail))
    else:
        err_code = str(exc.detail).split(":")[0] if ":" in str(exc.detail) else str(exc.detail)
        msg = str(exc.detail)

    payload = ErrorPayload(
        error_code=err_code,
        message_safe=msg,
        correlation_id=correlation_id,
        retryable=exc.status_code in [429, 502, 503, 504]
    )
    content = payload.model_dump()
    content["detail"] = exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )

# Tích hợp các module routers (P01 -> P09)
app.include_router(workspaces_router)
app.include_router(briefs_router)
app.include_router(sources_router)
app.include_router(ingestion_router)
app.include_router(research_router)
app.include_router(understanding_router)
app.include_router(retrieval_router)
app.include_router(ideation_router)
app.include_router(scripts_router)
app.include_router(feedback_router)
app.include_router(staging_router)
app.include_router(canary_router)
app.include_router(media_router)
app.include_router(jobs_router)
app.include_router(auth_router)
app.include_router(platform_config_router)
app.include_router(dieu_phoi_router)
