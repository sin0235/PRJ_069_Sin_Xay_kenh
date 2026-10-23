from src.modules.media_studio.prompt_compiler import video_prompt_compiler, CompiledVideoPrompt
# -*- coding: utf-8 -*-
"""Router API cho Phân hệ Media Studio (P1 Production Workflow).
Các route: /v1/media và /v1/ai-jobs
"""

import os
import subprocess
import sys
from pathlib import Path
import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.models.entities import (
    AIGenerationJob, MediaAsset, WorkspaceBudget, CostLedger,
    ProductionProject, TimelineVersion
)
from src.schemas.contracts import (
    MusicCapabilitiesResponse,
    MusicCapabilityItem,
    MusicProviderType,
    MusicGenerationMode,
    MusicJobStatus,
    MediaAssetOut,
    AIGenerationJobCreate,
    AIGenerationJobOut,
    ProductionProjectCreate,
    ProductionProjectOut,
    TimelineDocument,
    TimelineVersionOut,
    TimelineSaveRequest,
    TimelineClip,
    TimelineAudioTrack,
    TimelineCaption,
)

from src.modules.media_studio.service import media_service
from src.modules.media_studio.job_engine import job_engine
from src.modules.media_studio.music_provider import music_orchestrator
from src.modules.media_studio.video_provider import video_orchestrator
from session_manager import FlowLoginRequired, LOCAL_BROWSER_PROFILE_DIR
from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.video_processor import video_processor
from src.modules.media_studio.security import (
    get_workspace_storage_dir, MEDIA_ROOT_DIR, UPLOAD_SIZE_LIMITS,
    validate_audio_or_media_file,
)

media_router = APIRouter(prefix="/v1/media", tags=["Media Studio"])
jobs_router = APIRouter(prefix="/v1/ai-jobs", tags=["AI Generation Jobs"])
FLOW_SESSION_MANAGER = Path(__file__).resolve().parents[4] / "cong_cu_tu_dong" / "flow_bridge" / "session_manager.py"


def _flow_login_session_running() -> bool:
    if sys.platform != "linux" or not Path("/proc").is_dir():
        return False
    profile_arg = b"--user-data-dir=" + os.fsencode(LOCAL_BROWSER_PROFILE_DIR)
    for process in Path("/proc").iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            if any(profile_arg in arg for arg in (process / "cmdline").read_bytes().split(b"\0")):
                return True
        except OSError:
            continue
    return False


@media_router.post("/projects", response_model=ProductionProjectOut, status_code=status.HTTP_201_CREATED)
def create_media_project(
    payload: ProductionProjectCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    return media_service.create_project(db, tenant.workspace_id, tenant.user_id, payload)


@media_router.get("/projects", response_model=List[ProductionProjectOut])
def list_media_projects(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read"))
):
    return media_service.list_projects(db, tenant.workspace_id)


@media_router.post("/flow/login")
def open_google_flow_login(
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    """Mở tiện ích đăng nhập Flow trên máy chủ đang chạy ứng dụng."""
    if not tenant.dev_auth_bypass and not any(
        role.get("role_code") == "WORKSPACE_OWNER" and role.get("scope_type") == "WORKSPACE"
        for role in tenant.actor.roles
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ chủ workspace được mở phiên Google Flow.")
    if sys.platform == "win32":
        login_script = Path(__file__).resolve().parents[5] / "00_DANG_NHAP_GOOGLE_FLOW.cmd"
        if not login_script.is_file():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Không tìm thấy tiện ích đăng nhập Google Flow.")
        os.startfile(str(login_script))
        return {"success": True, "message": "Đã mở Edge để đăng nhập Google Flow trên máy chạy dịch vụ."}

    if sys.platform != "linux":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Đăng nhập Flow chỉ hỗ trợ trên Windows và Linux.")
    if not FLOW_SESSION_MANAGER.is_file():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Không tìm thấy session manager của Google Flow.")
    if _flow_login_session_running():
        return {"success": True, "already_running": True, "message": "Cửa sổ đăng nhập Flow đã được mở."}

    try:
        subprocess.Popen(
            [sys.executable, str(FLOW_SESSION_MANAGER), "--background"],
            cwd=FLOW_SESSION_MANAGER.parent,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Không thể mở cửa sổ đăng nhập Flow.") from exc
    return {"success": True, "message": "Đã mở Edge. Đăng nhập Google rồi đóng cửa sổ để lưu phiên Flow."}

# ==============================================================================
# 1. Media Assets Endpoints
# ==============================================================================

@media_router.post("/upload", response_model=MediaAssetOut)
async def upload_asset(
    file: UploadFile = File(...),
    source_product: str = Form("UPLOAD"),
    project_id: Optional[str] = Form(None),
    expected_category: str = Form("audio"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Tải lên tệp media (âm thanh, stems, ảnh, video) với xác thực magic bytes (B04, B05).
    """
    content = await file.read()
    asset = media_service.upload_asset(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        filename=file.filename or "unknown",
        data=content,
        source_product=source_product,
        project_id=project_id,
        expected_category=expected_category
    )
    # Gán URL truy cập có thời hạn an toàn
    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out

@media_router.get("/assets", response_model=List[MediaAssetOut])
def list_assets(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read"))
):
    """Liệt kê danh sách tư liệu truyền thông trong workspace."""
    assets = media_service.list_assets(db, tenant.workspace_id, project_id, limit)
    result = []
    for a in assets:
        out = MediaAssetOut.model_validate(a)
        out.url = f"/v1/media/assets/{a.id}/download?ttl=3600"
        result.append(out)
    return result

@media_router.get("/assets/{asset_id}", response_model=MediaAssetOut)
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read"))
):
    """Lấy chi tiết tư liệu với kiểm tra phân tách đa khách thuê nghiêm ngặt (B02)."""
    asset = media_service.get_asset(db, tenant.workspace_id, asset_id)
    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out

@media_router.get("/assets/{asset_id}/download")
def download_asset(
    asset_id: str,
    ttl: Optional[int] = Query(None),
    token: Optional[str] = Query(None),
    download: bool = Query(False),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    """
    Stream hoặc download media asset với kiểm tra phân tách tenant (MF-01).
    Hỗ trợ header Range cho video seek trong trình phát HTML5.
    """
    import os
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.workspace_id == tenant.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên media.")

    file_path = MEDIA_ROOT_DIR / asset.storage_key
    if not file_path.exists():
        file_path = MEDIA_ROOT_DIR / "workspaces" / asset.workspace_id / "media" / os.path.basename(asset.storage_key)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Tệp không tồn tại trên hệ thống lưu trữ: {asset.storage_key}")

    # Xác định MIME type chính xác cho video/audio
    media_type = asset.mime_detected or "application/octet-stream"
    if str(file_path).endswith(".mp4"):
        media_type = "video/mp4"
    elif str(file_path).endswith(".mp3"):
        media_type = "audio/mpeg"

    filename = asset.original_filename or file_path.name
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
    }

    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename,
            headers=headers,
            content_disposition_type="attachment"
        )
    else:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            headers=headers,
            content_disposition_type="inline"
        )


@jobs_router.post("", response_model=AIGenerationJobOut)
def submit_ai_job(
    payload: AIGenerationJobCreate,
    budget_cap: Optional[float] = Query(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("ai_job.create"))
):
    """
    Tiếp nhận tác vụ sinh media AI (B03 Idempotency, B07 Budget, B08 Credentials).
    """
    job = job_engine.submit_job(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        payload=payload,
        budget_cap=budget_cap
    )
    return job

@jobs_router.get("/{job_id}", response_model=AIGenerationJobOut)
def get_ai_job(
    job_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("ai_job.read"))
):
    """Lấy trạng thái tác vụ với kiểm tra ranh giới tenant (B02)."""
    job = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "JOB_NOT_FOUND", "message": "Không tìm thấy tác vụ AI."}
        )
    if job.workspace_id != tenant.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "JOB_NOT_FOUND", "message": "Không tìm thấy tác vụ AI."}
        )
    return job

# ==============================================================================
# 3. Music Generation & Audio Ducking Endpoints (P08 + GF04)
# ==============================================================================

@media_router.get("/music/capabilities", response_model=MusicCapabilitiesResponse)
def get_music_capabilities(
    tenant: TenantContext = Depends(require_action("media.read"))
):
    """Kiểm tra năng lực các nhà cung cấp âm nhạc AI (GF04)."""
    return music_orchestrator.get_capabilities(tenant.workspace_id)


@media_router.get("/music/jobs/{idempotency_key}")
def get_music_generation_status(
    idempotency_key: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    """Tra cứu trạng thái và asset nhạc đã lưu để khôi phục phản hồi bị mất."""
    job = db.query(AIGenerationJob).filter(
        AIGenerationJob.workspace_id == tenant.workspace_id,
        AIGenerationJob.asset_type == "MUSIC",
        AIGenerationJob.idempotency_key == idempotency_key,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail={"error_code": "JOB_NOT_FOUND", "message": "Không tìm thấy tác vụ âm nhạc."})

    asset = None
    if job.state == "SUCCEEDED":
        try:
            asset_ids = json.loads(job.output_asset_ids_json or "[]")
        except (TypeError, ValueError):
            asset_ids = []
        if asset_ids:
            asset = db.query(MediaAsset).filter(
                MediaAsset.id == asset_ids[0],
                MediaAsset.workspace_id == tenant.workspace_id,
            ).first()
        if asset:
            asset = MediaAssetOut.model_validate(asset)
            asset.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"

    return {
        "job_id": job.id,
        "state": job.state,
        "provider": job.provider,
        "model_id": job.model_id,
        "credits_source": job.credits_source,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "asset": asset,
    }


@media_router.post("/music/generate", response_model=MediaAssetOut)
def generate_music_track(
    prompt: str = Form(...),
    genre: str = Form("Pop"),
    mood: str = Form("Upbeat"),
    lyrics: Optional[str] = Form(None),
    use_official_lyria: bool = Form(False),
    provider: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    duration_sec: int = Form(30),
    project_id: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    normalize_tiktok: bool = Form(True),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Sinh bài hát/âm nhạc qua Google Lyria Official API, Flow Browser Pilot hoặc Local Test Synth.
    Tự động chuẩn hóa âm lượng và kiểm định chất lượng EBU R128 (-14 LUFS ± 1 LUFS) chuẩn TikTok (GF04).
    Bảo vệ lũy đẳng bền vững (Persistent Idempotency) và rào chắn Bốn Mắt (Separation of Duties).
    """
    # 1. Xác định Provider & Mode (Hỗ trợ an toàn cả Dependency Injection lẫn gọi trực tiếp test)
    lyrics = lyrics if isinstance(lyrics, str) else None
    project_id = project_id if isinstance(project_id, str) else None
    idempotency_key = idempotency_key if isinstance(idempotency_key, str) else None
    provider = provider if isinstance(provider, str) else None
    mode = mode if isinstance(mode, str) else None

    duration_val = 30
    if isinstance(duration_sec, (int, float)):
        duration_val = int(duration_sec)
    elif isinstance(duration_sec, str) and duration_sec.isdigit():
        duration_val = int(duration_sec)
    elif hasattr(duration_sec, "default") and isinstance(duration_sec.default, (int, float)):
        duration_val = int(duration_sec.default)

    use_official = bool(use_official_lyria) if not hasattr(use_official_lyria, "default") else bool(use_official_lyria.default)
    normalize_val = bool(normalize_tiktok) if not hasattr(normalize_tiktok, "default") else bool(normalize_tiktok.default)

    target_provider = None
    if provider and isinstance(provider, str) and provider.strip():
        try:
            target_provider = MusicProviderType(provider.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_PROVIDER", "message": f"Nhà cung cấp '{provider}' không hợp lệ."}
            )
    else:
        # Nếu không chỉ định provider tường minh:
        if use_official:
            target_provider = MusicProviderType.GOOGLE_OFFICIAL
        elif os.getenv("TESTING") == "1" or os.getenv("APP_ENV") == "test":
            target_provider = MusicProviderType.LOCAL_TEST_SYNTH
        else:
            # Mặc định an toàn cho nút không trả phí: FLOW_BROWSER_PILOT (tuyệt đối không tự nhảy sang Lyria trả phí)
            target_provider = MusicProviderType.FLOW_BROWSER_PILOT

    if mode and isinstance(mode, str) and mode.strip():
        try:
            target_mode = MusicGenerationMode(mode.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_MODE", "message": f"Chế độ '{mode}' không hợp lệ."}
            )
    else:
        if target_provider == MusicProviderType.FLOW_BROWSER_PILOT:
            target_mode = MusicGenerationMode.PILOT_ASSISTED
        else:
            target_mode = MusicGenerationMode.CLIP_30S

    # 2. Xử lý Lũy đẳng toàn diện (Full-Payload Persistent Idempotency)
    import json
    canonical_payload = {
        "prompt": prompt.strip(),
        "genre": genre.strip(),
        "mood": mood.strip(),
        "lyrics": (lyrics or "").strip(),
        "provider": target_provider.value,
        "mode": target_mode.value,
        "duration_sec": duration_val,
        "project_id": (project_id or "").strip(),
        "normalize_tiktok": normalize_val
    }
    canonical_json = json.dumps(canonical_payload, sort_keys=True)

    existing_job = None
    if idempotency_key and db:
        existing_job = db.query(AIGenerationJob).filter(
            AIGenerationJob.workspace_id == tenant.workspace_id,
            AIGenerationJob.idempotency_key == idempotency_key
        ).first()

        if existing_job:
            try:
                old_payload = json.loads(existing_job.request_payload_json)
                for field_name, expected_val in canonical_payload.items():
                    if old_payload.get(field_name) != expected_val:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={
                                "error_code": "IDEMPOTENCY_CONFLICT",
                                "message": f"Khóa idempotency_key '{idempotency_key}' đã tồn tại với tham số yêu cầu khác ({field_name})."
                            }
                        )
            except HTTPException:
                raise
            except Exception:
                pass

            if existing_job.state == "SUCCEEDED":
                try:
                    output_ids = json.loads(existing_job.output_asset_ids_json)
                    if output_ids:
                        asset = db.query(MediaAsset).filter(
                            MediaAsset.id == output_ids[0],
                            MediaAsset.workspace_id == tenant.workspace_id
                        ).first()
                        if asset:
                            out = MediaAssetOut.model_validate(asset)
                            out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
                            return out
                except Exception:
                    pass

            elif existing_job.state in ("SUBMITTING", "RUNNING"):
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail={
                        "error_code": "JOB_IN_PROGRESS",
                        "message": "Tác vụ đang được xử lý trong hàng đợi. Vui lòng chờ kết quả, không gửi trùng lặp.",
                        "job_id": existing_job.id,
                        "state": existing_job.state
                    }
                )

            elif existing_job.state == "NEEDS_RECONCILIATION":
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail={
                        "error_code": "NEEDS_RECONCILIATION",
                        "message": "Tác vụ đang chờ đối soát hóa đơn mạng từ nhà cung cấp. Không gửi lại yêu cầu mới.",
                        "job_id": existing_job.id,
                        "state": existing_job.state
                    }
                )

    # 3. Kiểm soát ngân sách nguyên tử (Preflight Reservation Check - Quyết toán sau khi thành công)
    estimated_cost = 0.03 if target_mode == MusicGenerationMode.CLIP_30S else 0.08
    if target_provider in (MusicProviderType.FLOW_BROWSER_PILOT, MusicProviderType.LOCAL_TEST_SYNTH):
        estimated_cost = 0.0

    if db and estimated_cost > 0.0:
        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == tenant.workspace_id).first()
        if budget and budget.hard_limit_units > 0.0:
            if (budget.spent_units + estimated_cost) > budget.hard_limit_units:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={"error_code": "QUOTA_EXCEEDED", "message": f"Vượt quá hạn ngạch ngân sách workspace ({budget.spent_units:.2f}/{budget.hard_limit_units:.2f})."}
                )

    # 4. Ghi nhận Job SUBMITTING
    job_record = None
    if idempotency_key and db:
        job_record = AIGenerationJob(
            workspace_id=tenant.workspace_id,
            project_id=project_id,
            asset_type="MUSIC",
            provider=target_provider.value,
            provider_mode=target_mode.value,
            model_id="flow-music-web" if target_provider == MusicProviderType.FLOW_BROWSER_PILOT else (
                "lyria-3-clip-preview" if target_mode == MusicGenerationMode.CLIP_30S else "lyria-3.5"
            ),
            credits_source="FLOW_MUSIC_PLUS" if target_provider == MusicProviderType.FLOW_BROWSER_PILOT else "API_BILLING",
            idempotency_key=idempotency_key,
            state="SUBMITTING",
            request_payload_json=canonical_json,
            estimated_cost=estimated_cost,
            created_by=tenant.user_id
        )
        db.add(job_record)
        db.commit()

    # 5. Thực thi sinh nhạc qua Orchestrator
    try:
        asset = music_orchestrator.generate_music_track(
            db=db,
            workspace_id=tenant.workspace_id,
            user_id=tenant.user_id,
            prompt=prompt,
            genre=genre,
            mood=mood,
            lyrics=lyrics,
            duration_sec=duration_val,
            provider=target_provider,
            mode=target_mode,
            project_id=project_id,
            idempotency_key=idempotency_key
        )

        # 6. Quyết toán ngân sách thực tế CHỈ KHI tác vụ SUCCEEDED (Settlement on Success)
        actual_cost = estimated_cost
        if db and actual_cost > 0.0:
            budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == tenant.workspace_id).first()
            if budget:
                budget.spent_units += actual_cost
                db.commit()

        if job_record:
            job_record.state = "SUCCEEDED"
            job_record.output_asset_ids_json = json.dumps([asset.id])
            job_record.actual_cost = actual_cost
            db.commit()

        out = MediaAssetOut.model_validate(asset)
        out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
        return out

    except FlowLoginRequired as exc:
        if job_record:
            job_record.state = "FAILED"
            job_record.error_code = "FLOW_LOGIN_REQUIRED"
            db.commit()
        raise HTTPException(status_code=401, detail={"error_code": "FLOW_LOGIN_REQUIRED", "message": "Chưa đăng nhập tài khoản Google Flow. Hãy đăng nhập rồi thử lại."}) from exc
    except Exception as exc:
        msg = str(exc)
        if job_record:
            if "UPSTREAM_TIMEOUT" in msg:
                job_record.state = "NEEDS_RECONCILIATION"
                job_record.error_code = "UPSTREAM_TIMEOUT"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail={"error_code": "NEEDS_RECONCILIATION", "message": "Yêu cầu đã gửi tới nhà cung cấp nhưng gặp timeout mạng. Đang chờ tra soát đối chiếu hóa đơn."}
                )
            job_record.state = "FAILED"
            job_record.error_message = msg
            db.commit()

        if "PROMPT_SAFETY_VIOLATION" in msg:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error_code": "PROMPT_SAFETY_VIOLATION", "message": msg})
        if "CREDENTIALS_MISSING" in msg or "CREDENTIALS_INVALID" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"error_code": "CREDENTIALS_MISSING", "message": msg})
        if "MODEL_UNAVAILABLE" in msg or "REGION_UNAVAILABLE" in msg:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"error_code": "MODEL_UNAVAILABLE", "message": msg})
        if "QUOTA_EXCEEDED" in msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"error_code": "QUOTA_EXCEEDED", "message": msg})
        if "AUDIO_QC_FAILED" in msg:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"error_code": "AUDIO_QC_FAILED", "message": msg})

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "MUSIC_GENERATION_FAILED", "message": msg})


@media_router.post("/assets/{asset_id}/review", response_model=MediaAssetOut)
def review_media_asset(
    asset_id: str,
    decision: str = Form(..., description="Quyết định: APPROVE hoặc REJECT"),
    review_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Phê duyệt tư liệu truyền thông theo nguyên tắc Bốn Mắt (Separation of Duties).
    Người tạo không được phép tự phê duyệt tư liệu của chính mình sang APPROVED.
    """
    if decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "INVALID_DECISION", "message": "Quyết định phải là APPROVE hoặc REJECT."})

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.workspace_id == tenant.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "ASSET_NOT_FOUND", "message": "Không tìm thấy tư liệu."})

    # Separation of duties: creator cannot self-approve
    if decision == "APPROVE" and asset.created_by == tenant.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "SEPARATION_OF_DUTIES_VIOLATION", "message": "Người tạo không được phép tự phê duyệt tư liệu của chính mình."}
        )

    asset.approval_state = "APPROVED" if decision == "APPROVE" else "REJECTED"
    db.commit()
    db.refresh(asset)
    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out

@media_router.post("/audio/mix", response_model=MediaAssetOut)
def mix_voice_and_music(
    voice_asset_id: str = Form(...),
    music_asset_id: str = Form(...),
    music_attenuation_db: float = Form(-18.0),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Tự động hòa âm (Mix audio) với kỹ thuật Auto-Ducking:
    Hạ âm lượng nhạc nền (-18dB) khi có giọng đọc thuyết minh để nổi bật lời thoại.
    """
    from src.models.entities import MediaAsset
    import uuid, hashlib

    voice = db.query(MediaAsset).filter(
        MediaAsset.id == voice_asset_id, MediaAsset.workspace_id == tenant.workspace_id
    ).first()
    music = db.query(MediaAsset).filter(
        MediaAsset.id == music_asset_id, MediaAsset.workspace_id == tenant.workspace_id
    ).first()

    if not voice or not music:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ASSET_NOT_FOUND", "message": "Không tìm thấy tư liệu âm thanh."}
        )

    voice_path = MEDIA_ROOT_DIR / voice.storage_key
    music_path = MEDIA_ROOT_DIR / music.storage_key

    out_filename = f"mixed_{uuid.uuid4().hex[:12]}.mp3"
    out_dir = get_workspace_storage_dir(tenant.workspace_id)
    out_path = out_dir / out_filename

    try:
        audio_processor.apply_auto_ducking(
            voice_path=voice_path,
            music_path=music_path,
            output_path=out_path,
            music_attenuation_db=music_attenuation_db
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "AUDIO_MIX_FAILED", "message": f"Không thể hòa âm tự động: {exc}"}
        ) from exc

    data = out_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    mixed_asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=tenant.workspace_id,
        storage_key=f"workspaces/{tenant.workspace_id}/media/{out_filename}",
        sha256=sha,
        byte_size=len(data),
        mime_detected="audio/mpeg",
        source_product="AUDIO_MIXER_DUCKING",
        original_filename=out_filename,
        created_by=tenant.user_id,
        approval_state="APPROVED"
    )
    db.add(mixed_asset)
    db.commit()
    db.refresh(mixed_asset)

    out = MediaAssetOut.model_validate(mixed_asset)
    out.url = f"/v1/media/assets/{mixed_asset.id}/download?ttl=3600"
    return out

# ==============================================================================
# 4. Video Generation & TikTok 9:16 Assembly Endpoints (P09 + GF01/02/03)
# ==============================================================================


@media_router.post("/video/expand", response_model=MediaAssetOut)
async def expand_existing_16_9_video(
    file: Optional[UploadFile] = File(None),
    asset_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    blur_strength: int = Form(25),
    remove_watermark: bool = Form(True),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Mo rong video goc 16:9 (tu Google Flow / Omni 10s hoac nguoi dung tai len)
    thanh video doc 9:16 (1080x1920) chuan TikTok bang cong nghe Blurred Backdrop Canvas Extension.
    Bao toan 100% thoi luong goc (10s), do net va mau sac cua video Omni.
    """
    import uuid, hashlib
    project_id = project_id if isinstance(project_id, str) and project_id.strip() else None
    if project_id and db and not db.query(ProductionProject.id).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == tenant.workspace_id
    ).first():
        raise HTTPException(status_code=404, detail={"error_code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án trong workspace."})

    out_dir = get_workspace_storage_dir(tenant.workspace_id)
    input_path = None
    temp_input_path = None
    parent_asset_id = None

    if file and file.filename:
        file_bytes = await file.read(UPLOAD_SIZE_LIMITS["video"] + 1)
        validate_audio_or_media_file(file_bytes, file.filename, expected_category="video")
        temp_input_path = out_dir / f"flow_raw_16_9_{uuid.uuid4().hex}.mp4"
        temp_input_path.write_bytes(file_bytes)
        input_path = temp_input_path
    elif asset_id:
        existing = db.query(MediaAsset).filter(
            MediaAsset.id == asset_id, MediaAsset.workspace_id == tenant.workspace_id
        ).first()
        if not existing or not existing.mime_detected.startswith("video/"):
            raise HTTPException(status_code=404, detail="Không tìm thấy video nguồn trong workspace.")
        if existing.project_id and existing.project_id != project_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy video nguồn trong dự án.")
        parent_asset_id = existing.id
        input_path = MEDIA_ROOT_DIR / existing.storage_key
        if not input_path.exists():
            input_path = out_dir / existing.original_filename
    else:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp tệp video hoặc asset_id.")

    expanded_filename = f"flow_expanded_9_16_{uuid.uuid4().hex[:10]}.mp4"
    expanded_path = out_dir / expanded_filename
    try:
        if not input_path or not input_path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp video nguồn trên hệ thống.")
        meta = video_processor.expand_16_9_to_9_16(
            input_video_path=input_path,
            output_video_path=expanded_path,
            blur_strength=blur_strength,
            remove_watermark=remove_watermark
        )
        data = expanded_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()

        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=tenant.workspace_id,
            project_id=project_id,
            parent_asset_id=parent_asset_id,
            storage_key=f"workspaces/{tenant.workspace_id}/media/{expanded_filename}",
            sha256=sha,
            byte_size=len(data),
            mime_detected="video/mp4",
            source_product="FLOW_OMNI_EXPANDED_9_16",
            original_filename=expanded_filename,
            created_by=tenant.user_id,
            duration_ms=int(meta.get("duration_seconds", 10.0) * 1000),
            approval_state="UNREVIEWED"
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
    except Exception:
        if expanded_path.exists():
            expanded_path.unlink()
        raise
    finally:
        if temp_input_path and temp_input_path.exists():
            temp_input_path.unlink()

    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out




@media_router.post("/video/remove-watermark", response_model=MediaAssetOut)
async def remove_watermark_from_video(
    file: Optional[UploadFile] = File(None),
    asset_id: Optional[str] = Form(None),
    use_cpu: bool = Form(True),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Khử sạch logo / watermark Google Veo & Gemini AI khỏi video
    bằng công nghệ Reverse Alpha Blending & NCNN AI Denoiser (VeoWatermarkRemover v0.6.5).
    Đảm bảo video sạch 100%, không còn logo AI gây phản cảm cho người xem.
    """
    import uuid, hashlib
    out_dir = get_workspace_storage_dir(tenant.workspace_id)
    input_path = None
    original_name = "video.mp4"

    if file and file.filename:
        file_bytes = await file.read()
        tmp_name = f"raw_for_clean_{uuid.uuid4().hex[:8]}_{file.filename}"
        input_path = out_dir / tmp_name
        input_path.write_bytes(file_bytes)
        original_name = file.filename
    elif asset_id:
        existing = db.query(MediaAsset).filter(
            MediaAsset.id == asset_id, MediaAsset.workspace_id == tenant.workspace_id
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy video nguồn.")
        input_path = MEDIA_ROOT_DIR / existing.storage_key
        if not input_path.exists():
            input_path = out_dir / existing.original_filename
        original_name = existing.original_filename or f"asset_{asset_id}.mp4"
    else:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp file video hoặc asset_id.")

    if not input_path or not input_path.exists():
        raise HTTPException(status_code=404, detail="Tập tin video nguồn không tồn tại trên hệ thống.")

    clean_filename = f"veo_cleaned_{uuid.uuid4().hex[:10]}.mp4"
    clean_path = out_dir / clean_filename

    try:
        res = video_processor.remove_veo_watermark(
            input_video_path=input_path,
            output_video_path=clean_path,
            use_cpu=use_cpu
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khử watermark Veo: {exc}"
        ) from exc

    meta = video_processor.probe_video(clean_path)
    data = clean_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=tenant.workspace_id,
        storage_key=f"workspaces/{tenant.workspace_id}/media/{clean_filename}",
        sha256=sha,
        byte_size=len(data),
        mime_detected="video/mp4",
        source_product="VEO_WATERMARK_CLEANED",
        original_filename=f"clean_{original_name}",
        created_by=tenant.user_id,
        duration_ms=int(meta.get("duration_seconds", 0.0) * 1000),
        approval_state="APPROVED"
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out

@media_router.post("/video/prompt/compile", response_model=CompiledVideoPrompt)
def compile_video_prompt(
    prompt: str = Form(...),
    aspect_ratio: str = Form("16:9"),
    duration_seconds: int = Form(10),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Biên dịch yêu cầu của người dùng thành Bộ lệnh video đa tầng và Hướng dẫn phân cảnh chi tiết.
    """
    return video_prompt_compiler.compile(
        user_prompt=prompt,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds
    )

@media_router.post("/video/generate", response_model=MediaAssetOut)
def generate_video_scene(
    prompt: str = Form(...),
    aspect_ratio: str = Form("9:16"),
    use_official_omni: bool = Form(False),
    project_id: Optional[str] = Form(None),
    start_image_asset_id: Optional[str] = Form(None),
    remove_watermark: bool = Form(False),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Sinh video phân cảnh tỷ lệ dọc 9:16 qua Google Flow (Zero-cost 0đ) hoặc Gemini Omni Flash.
    """
    project_id = project_id if isinstance(project_id, str) and project_id.strip() else None
    start_image_asset_id = start_image_asset_id if isinstance(start_image_asset_id, str) and start_image_asset_id.strip() else None

    if project_id and db and not db.query(ProductionProject.id).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == tenant.workspace_id
    ).first():
        raise HTTPException(status_code=404, detail={"error_code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án trong workspace."})

    start_image_path = None
    if start_image_asset_id:
        image_asset = db.query(MediaAsset).filter(
            MediaAsset.id == start_image_asset_id,
            MediaAsset.workspace_id == tenant.workspace_id,
        ).first()
        if not image_asset or not image_asset.mime_detected.startswith("image/"):
            raise HTTPException(status_code=404, detail={"error_code": "IMAGE_NOT_FOUND", "message": "Không tìm thấy ảnh tham chiếu trong workspace."})
        if image_asset.project_id and image_asset.project_id != project_id:
            raise HTTPException(status_code=404, detail={"error_code": "IMAGE_NOT_FOUND", "message": "Không tìm thấy ảnh tham chiếu trong dự án."})
        start_image_path = (MEDIA_ROOT_DIR / image_asset.storage_key).resolve()
        if not start_image_path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or not start_image_path.is_file():
            raise HTTPException(status_code=404, detail={"error_code": "IMAGE_NOT_FOUND", "message": "Tệp ảnh tham chiếu không tồn tại."})

    try:
        asset = video_orchestrator.generate_video_scene(
            db=db,
            workspace_id=tenant.workspace_id,
            user_id=tenant.user_id,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            use_official_omni=use_official_omni,
            start_image_path=start_image_path,
            start_image_asset_id=start_image_asset_id,
            project_id=project_id,
            remove_watermark=remove_watermark
        )
    except FlowLoginRequired as ex:
        raise HTTPException(status_code=401, detail={"error_code": "FLOW_LOGIN_REQUIRED", "message": "Chưa đăng nhập tài khoản Google Flow. Hãy đăng nhập rồi thử lại."}) from ex
    except RuntimeError as ex:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ex))
    out = MediaAssetOut.model_validate(asset)
    out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
    return out

@media_router.post("/video/assemble", response_model=MediaAssetOut)
def assemble_tiktok_video(
    scene_asset_ids_json: str = Form(..., description="JSON array of scene MediaAsset IDs"),
    audio_asset_id: str = Form(..., description="Audio track MediaAsset ID"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Ghép chuỗi phân cảnh video dọc 9:16 cùng bản mix âm thanh thành video TikTok hoàn chỉnh.
    """
    import json, uuid, hashlib
    from src.models.entities import MediaAsset

    try:
        scene_ids = json.loads(scene_asset_ids_json)
        if not isinstance(scene_ids, list) or len(scene_ids) == 0:
            raise ValueError("scene_asset_ids_json phải là mảng JSON chứa ít nhất 1 asset ID.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SCENE_IDS", "message": f"Danh sách scene IDs không hợp lệ: {exc}"}
        ) from exc

    # Kiểm tra các assets thuộc workspace
    scene_paths = []
    for sid in scene_ids:
        a = db.query(MediaAsset).filter(
            MediaAsset.id == sid, MediaAsset.workspace_id == tenant.workspace_id
        ).first()
        if not a:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SCENE_NOT_FOUND", "message": f"Không tìm thấy scene asset: {sid}"}
            )
        scene_paths.append(MEDIA_ROOT_DIR / a.storage_key)

    audio = db.query(MediaAsset).filter(
        MediaAsset.id == audio_asset_id, MediaAsset.workspace_id == tenant.workspace_id
    ).first()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AUDIO_NOT_FOUND", "message": f"Không tìm thấy audio asset: {audio_asset_id}"}
        )
    audio_path = MEDIA_ROOT_DIR / audio.storage_key

    out_filename = f"tiktok_assembled_{uuid.uuid4().hex[:12]}.mp4"
    out_dir = get_workspace_storage_dir(tenant.workspace_id)
    out_path = out_dir / out_filename

    try:
        meta = video_processor.assemble_scenes_with_audio(
            scene_video_paths=scene_paths,
            audio_path=audio_path,
            output_path=out_path
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ASSEMBLE_FAILED", "message": f"Lỗi ghép nối video: {exc}"}
        ) from exc

    data = out_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    assembled_asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=tenant.workspace_id,
        storage_key=f"workspaces/{tenant.workspace_id}/media/{out_filename}",
        sha256=sha,
        byte_size=len(data),
        mime_detected="video/mp4",
        source_product="TIKTOK_ASSEMBLY",
        original_filename=out_filename,
        created_by=tenant.user_id,
        duration_ms=int(meta["duration_seconds"] * 1000),
        approval_state="APPROVED"
    )
    db.add(assembled_asset)
    db.commit()
    db.refresh(assembled_asset)

    out = MediaAssetOut.model_validate(assembled_asset)
    out.url = f"/v1/media/assets/{assembled_asset.id}/download?ttl=3600"
    return out


# ==============================================================================
# M-P3 & M-P5: Timeline Management & Render Endpoints
# ==============================================================================

@media_router.get("/projects/{project_id}/timeline", response_model=TimelineVersionOut)
def get_project_timeline(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read"))
):
    """
    Lấy phiên bản timeline mới nhất của dự án (M-P3).
    Kiểm tra bảo vệ ranh giới tenant/workspace nghiêm ngặt.
    """
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == tenant.workspace_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROJECT_NOT_FOUND", "message": f"Không tìm thấy dự án {project_id} trong workspace."}
        )

    latest = db.query(TimelineVersion).filter(
        TimelineVersion.project_id == project_id
    ).order_by(TimelineVersion.version.desc()).first()

    if not latest:
        empty_doc = TimelineDocument()
        return TimelineVersionOut(
            id=f"timeline-init-{project_id}",
            project_id=project_id,
            version=0,
            timeline=empty_doc,
            is_locked=False,
            created_by="system",
            created_at=datetime.now(timezone.utc)
        )

    try:
        doc_dict = json.loads(latest.tracks_json)
        doc = TimelineDocument.model_validate(doc_dict)
    except Exception:
        doc = TimelineDocument()

    return TimelineVersionOut(
        id=latest.id,
        project_id=latest.project_id,
        version=latest.version,
        timeline=doc,
        is_locked=latest.is_locked,
        created_by=latest.created_by,
        created_at=latest.created_at
    )


@media_router.put("/projects/{project_id}/timeline", response_model=TimelineVersionOut)
def save_project_timeline(
    project_id: str,
    payload: TimelineSaveRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Lưu phiên bản timeline mới bất biến (M-P3).
    - Kiểm soát OCC Conflict: trả HTTP 409 nếu expected_version không khớp version hiện tại.
    - Không sửa phiên bản đã khóa.
    - Kiểm tra mọi asset ID thuộc đúng workspace.
    - Validate trim, duration.
    """
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == tenant.workspace_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROJECT_NOT_FOUND", "message": f"Không tìm thấy dự án {project_id} trong workspace."}
        )

    latest = db.query(TimelineVersion).filter(
        TimelineVersion.project_id == project_id
    ).order_by(TimelineVersion.version.desc()).first()

    if latest:
        if latest.is_locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TIMELINE_LOCKED", "message": f"Phiên bản timeline v{latest.version} đã bị khóa, không thể chỉnh sửa."}
            )
        if payload.expected_version is not None and payload.expected_version != latest.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "STALE_VERSION_CONFLICT",
                    "message": f"Xung đột phiên bản timeline (OCC): phiên bản hiện tại là {latest.version}, mong đợi {payload.expected_version}.",
                    "current_version": latest.version
                }
            )
        next_version = latest.version + 1
    else:
        if payload.expected_version is not None and payload.expected_version not in (0, None):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "STALE_VERSION_CONFLICT",
                    "message": f"Xung đột phiên bản timeline: dự án chưa có timeline nhưng expected_version={payload.expected_version}.",
                    "current_version": 0
                }
            )
        next_version = 1

    # Validate asset IDs và trim/duration
    asset_ids_to_check = set()
    for clip in payload.timeline.clips:
        asset_ids_to_check.add(clip.asset_id)
        if clip.duration_ms <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_DURATION", "message": f"Clip {clip.clip_id}: duration_ms phải lớn hơn 0 ({clip.duration_ms})."}
            )
        if clip.trim_in_ms < 0 or clip.trim_out_ms < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_TRIM", "message": f"Clip {clip.clip_id}: trim_in_ms và trim_out_ms phải >= 0."}
            )
        if clip.media_type in ("video", TimelineClip) and clip.trim_out_ms > 0 and clip.trim_out_ms <= clip.trim_in_ms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_TRIM_RANGE", "message": f"Clip {clip.clip_id}: trim_out_ms ({clip.trim_out_ms}) phải lớn hơn trim_in_ms ({clip.trim_in_ms})."}
            )

    if payload.timeline.voice_track and payload.timeline.voice_track.asset_id:
        asset_ids_to_check.add(payload.timeline.voice_track.asset_id)
    if payload.timeline.music_track and payload.timeline.music_track.asset_id:
        asset_ids_to_check.add(payload.timeline.music_track.asset_id)

    if asset_ids_to_check:
        existing_assets = db.query(MediaAsset).filter(
            MediaAsset.id.in_(list(asset_ids_to_check)),
            MediaAsset.workspace_id == tenant.workspace_id
        ).all()
        asset_map = {a.id: a for a in existing_assets}
        missing_ids = asset_ids_to_check - set(asset_map.keys())
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ASSET_NOT_FOUND_OR_CROSS_WORKSPACE",
                    "message": f"Các asset sau không tồn tại hoặc không thuộc workspace của bạn: {list(missing_ids)}"
                }
            )

        # Kiểm tra trim_out_ms không được vượt quá thời lượng video nguồn
        for clip in payload.timeline.clips:
            asset = asset_map.get(clip.asset_id)
            if asset and asset.duration_ms and asset.duration_ms > 0:
                if clip.trim_out_ms > asset.duration_ms:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INVALID_TRIM_OUT",
                            "message": f"Clip {clip.clip_id}: Điểm ra trim_out_ms ({clip.trim_out_ms}ms) vượt quá thời lượng thực tế của video nguồn ({asset.duration_ms}ms)."
                        }
                    )

    new_ver = TimelineVersion(
        id=f"tl-{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        version=next_version,
        tracks_json=payload.timeline.model_dump_json(),
        is_locked=False,
        created_by=tenant.user_id,
        created_at=datetime.now(timezone.utc)
    )
    try:
        db.add(new_ver)
        db.commit()
        db.refresh(new_ver)
    except IntegrityError:
        db.rollback()
        latest_now = db.query(TimelineVersion).filter(
            TimelineVersion.project_id == project_id
        ).order_by(TimelineVersion.version.desc()).first()
        current_v = latest_now.version if latest_now else next_version
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "STALE_VERSION_CONFLICT",
                "message": f"Xung đột phiên bản timeline (OCC): Phiên bản v{next_version} đã được ghi đồng thời bởi một phiên khác. Vui lòng tải lại trang.",
                "current_version": current_v
            }
        )

    return TimelineVersionOut(
        id=new_ver.id,
        project_id=new_ver.project_id,
        version=new_ver.version,
        timeline=payload.timeline,
        is_locked=new_ver.is_locked,
        created_by=new_ver.created_by,
        created_at=new_ver.created_at
    )


@media_router.post("/projects/{project_id}/render-timeline", response_model=MediaAssetOut)
def render_project_timeline(
    project_id: str,
    timeline_version_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload"))
):
    """
    Render video MP4 chuẩn TikTok từ phiên bản timeline đã lưu (M-P5).
    - Concurrency = 1.
    - Chuẩn 1080x1920, 30fps, H.264/AAC.
    - Audio -14 LUFS ± 1 LUFS.
    - Trạng thái thành phẩm ban đầu: UNREVIEWED.
    """
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == tenant.workspace_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROJECT_NOT_FOUND", "message": f"Không tìm thấy dự án {project_id} trong workspace."}
        )

    if timeline_version_id:
        tv = db.query(TimelineVersion).filter(
            TimelineVersion.id == timeline_version_id,
            TimelineVersion.project_id == project_id
        ).first()
        if not tv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TIMELINE_VERSION_NOT_FOUND", "message": f"Không tìm thấy timeline version: {timeline_version_id}"}
            )
    else:
        tv = db.query(TimelineVersion).filter(
            TimelineVersion.project_id == project_id
        ).order_by(TimelineVersion.version.desc()).first()
        if not tv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "NO_TIMELINE_VERSION", "message": "Dự án chưa có phiên bản timeline nào được lưu."}
            )

    try:
        timeline_doc = TimelineDocument.model_validate_json(tv.tracks_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_TIMELINE_DATA", "message": f"Dữ liệu timeline không hợp lệ: {exc}"}
        )

    if not timeline_doc.clips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EMPTY_TIMELINE_CLIPS", "message": "Timeline không có phân cảnh nào để render."}
        )

    def resolve_asset_path(aid: str) -> Path:
        asset = db.query(MediaAsset).filter(
            MediaAsset.id == aid,
            MediaAsset.workspace_id == tenant.workspace_id
        ).first()
        if not asset:
            raise FileNotFoundError(f"Không tìm thấy asset {aid} trong workspace.")
        p = MEDIA_ROOT_DIR / asset.storage_key
        if not p.exists():
            p = MEDIA_ROOT_DIR / "workspaces" / asset.workspace_id / "media" / os.path.basename(asset.storage_key)
        if not p.exists():
            raise FileNotFoundError(f"Tệp asset không tồn tại trên ổ lưu trữ: {asset.storage_key}")
        return p

    out_filename = f"rendered_timeline_{project_id}_v{tv.version}_{uuid.uuid4().hex[:8]}.mp4"
    out_dir = get_workspace_storage_dir(tenant.workspace_id)
    out_path = out_dir / out_filename

    try:
        meta = video_processor.render_timeline_document(
            timeline=timeline_doc,
            asset_path_resolver=resolve_asset_path,
            output_path=out_path
        )
    except Exception as exc:
        if out_path.exists():
            out_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "RENDER_FAILED", "message": f"Lỗi render video: {exc}"}
        ) from exc

    data = out_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    rendered_asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=tenant.workspace_id,
        project_id=project_id,
        storage_key=f"workspaces/{tenant.workspace_id}/media/{out_filename}",
        sha256=sha,
        byte_size=len(data),
        mime_detected="video/mp4",
        source_product="TIMELINE_RENDER",
        original_filename=out_filename,
        created_by=tenant.user_id,
        duration_ms=int(meta.get("duration_seconds", 0) * 1000),
        approval_state="UNREVIEWED"
    )
    db.add(rendered_asset)
    db.commit()
    db.refresh(rendered_asset)

    out = MediaAssetOut.model_validate(rendered_asset)
    out.url = f"/v1/media/assets/{rendered_asset.id}/download?ttl=3600"
    return out

